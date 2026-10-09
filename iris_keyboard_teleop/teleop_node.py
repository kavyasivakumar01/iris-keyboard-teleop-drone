import math
import os
import select
import sys
import termios
import time
import tty

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist, PoseStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import SetMode, CommandBool, CommandTOL

TAKEOFF_ALT = 5.0   # metres
SPEED = 1.0         # forward/back, m/s
CLIMB = 0.5         # up/down, m/s
YAW_RATE = 0.8      # rad/s
HOLD_TIMEOUT = 0.5  # seconds a key counts as "held"

KEYS = {
    '\x1b[A': 'forward', '\x1b[B': 'back',
    '\x1b[D': 'yaw_left', '\x1b[C': 'yaw_right',
    'w': 'up', 'W': 'up', 's': 'down', 'S': 'down',
}


class TeleopNode(Node):
    def __init__(self):
        super().__init__('iris_teleop')
        self.state = State()
        self.yaw = 0.0
        self.z = 0.0
        self.action = None
        self.action_time = 0.0

        self.create_subscription(State, '/mavros/state', self.state_cb, 10)
        self.create_subscription(PoseStamped, '/mavros/local_position/pose',
                                 self.pose_cb, qos_profile_sensor_data)
        self.vel_pub = self.create_publisher(
            Twist, '/mavros/setpoint_velocity/cmd_vel_unstamped', 10)

        self.mode_client = self.create_client(SetMode, '/mavros/set_mode')
        self.arm_client = self.create_client(CommandBool, '/mavros/cmd/arming')
        self.takeoff_client = self.create_client(CommandTOL, '/mavros/cmd/takeoff')

        self.get_logger().info('Teleop node started')

    def state_cb(self, msg):
        self.state = msg

    def pose_cb(self, msg):
        q = msg.pose.orientation
        self.yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                              1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        self.z = msg.pose.position.z

    def call(self, client, request):
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        return future.result()

    def takeoff_sequence(self, altitude):
        self.get_logger().info('Waiting for drone connection...')
        while rclpy.ok() and not self.state.connected:
            rclpy.spin_once(self, timeout_sec=0.5)

        self.mode_client.wait_for_service()
        mode_req = SetMode.Request()
        mode_req.custom_mode = 'GUIDED'
        res = self.call(self.mode_client, mode_req)
        self.get_logger().info(f'GUIDED mode sent: {res.mode_sent}')

        if self.state.armed:
            self.get_logger().info('Already armed, skipping arm and takeoff')
            return

        arm_req = CommandBool.Request()
        arm_req.value = True
        res = self.call(self.arm_client, arm_req)
        self.get_logger().info(f'Armed: {res.success}')

        takeoff_req = CommandTOL.Request()
        takeoff_req.altitude = altitude
        res = self.call(self.takeoff_client, takeoff_req)
        self.get_logger().info(f'Takeoff accepted: {res.success}')

    def wait_for_altitude(self, altitude):
        self.get_logger().info('Climbing...')
        while rclpy.ok() and self.z < 0.9 * altitude:
            rclpy.spin_once(self, timeout_sec=0.5)
        self.get_logger().info(
            'Keyboard active: arrows = move/yaw, w/s = climb/descend')

    def start_control(self):
        self.create_timer(0.05, self.control_loop)  # 20 Hz

    def read_key(self):
        fd = sys.stdin.fileno()
        action = None
        while select.select([fd], [], [], 0)[0]:
            data = os.read(fd, 64).decode(errors='ignore')
            for seq, name in KEYS.items():
                if seq in data:
                    action = name
        return action

    def control_loop(self):
        now = time.time()
        pressed = self.read_key()
        if pressed:
            self.action, self.action_time = pressed, now
        active = self.action if now - self.action_time < HOLD_TIMEOUT else None

        fwd = up = yaw = 0.0
        if active == 'forward':
            fwd = SPEED
        elif active == 'back':
            fwd = -SPEED
        elif active == 'up':
            up = CLIMB
        elif active == 'down':
            up = -CLIMB
        elif active == 'yaw_left':
            yaw = YAW_RATE
        elif active == 'yaw_right':
            yaw = -YAW_RATE

        msg = Twist()
        msg.linear.x = fwd * math.cos(self.yaw)
        msg.linear.y = fwd * math.sin(self.yaw)
        msg.linear.z = up
        msg.angular.z = yaw
        self.vel_pub.publish(msg)


def main():
    rclpy.init()
    node = TeleopNode()
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        node.takeoff_sequence(TAKEOFF_ALT)
        node.wait_for_altitude(TAKEOFF_ALT)
        tty.setcbreak(sys.stdin.fileno())
        node.start_control()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()