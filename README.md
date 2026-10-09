# iris-keyboard-teleop-drone
## Overview
When the node starts, it puts the drone in GUIDED mode, arms it, and takes off to a fixed altitude of 5 m. After that it reads the keyboard and sends velocity commands so you can fly the drone yourself. If no key is pressed, the drone just hovers where it is.

## Controls
Click the terminal running the node first, otherwise it won't get your key presses.
| Key | Action |
|---|---|
| Up / Down arrow | Move forward / backward |
| Left / Right arrow | Yaw left / right |
| W / S | Climb / descend |
| No key | Hover in place |

## My understanding
### How the pieces fit together
Keyboard -> teleop node -> MAVROS -> ArduPilot SITL <-> Gazebo (Iris)
- **Gazebo Harmonic** is the simulator. It draws the world and handles the drone's physics.
- **ArduPilot SITL** is the drone's flight controller software, running on my laptop instead of on real hardware. It keeps the drone stable, controls the motors and holds position. The `ardupilot_gazebo` plugin connects it to Gazebo: Gazebo sends it sensor data and it sends motor commands back.
- **MAVROS** is the bridge. It turns ArduPilot's MAVLink messages into ROS 2 topics and services. My node only ever talks to MAVROS.
### What the node does
**Startup.** The node subscribes to `/mavros/state` and waits until `connected` is true. Then it calls three services:
- `/mavros/set_mode` to switch to GUIDED, because ArduPilot only accepts outside velocity commands in this mode
- `/mavros/cmd/arming` to arm the motors
- `/mavros/cmd/takeoff` to climb to 5 m

I used services for these because they're one-time actions and I want to know if they worked. If the drone is already armed, the node skips arming and takeoff, which lets me restart it mid-flight. After the takeoff command it watches `/mavros/local_position/pose` and only turns the keyboard on once the drone is at about 90% of the target height.

**Flying.** A timer runs 20 times a second. Each time, it reads the keyboard, works out what the drone should be doing, and publishes a velocity (`Twist`) to `/mavros/setpoint_velocity/cmd_vel_unstamped`. A topic makes sense here since it's a constant stream of commands.

### Things I had to figure out
- **Hovering.** When no key is pressed, the node sends zero velocity. In GUIDED mode that makes ArduPilot hold its position, so the drone hovers. The node has to keep sending it even when idle, because ArduPilot stops following velocity commands if they stop arriving.
- **Key release.** A terminal only sends characters while a key is held down and never tells you when it's released. So I count a key as held for 0.5 s after its last character (`HOLD_TIMEOUT`), and after that it's treated as released.
- **Reading the keyboard.** The terminal is switched to cbreak mode so each key arrives right away without pressing Enter, and the old settings are restored when the node exits. The arrow keys arrive as three characters (`ESC [ A`, `B`, `C`, `D`), while W and S are single characters.
- **Forward means where the drone is facing.** MAVROS wants velocities in the world frame, so I rotate the forward speed `v` by the drone's yaw: `vx = v*cos(yaw)`, `vy = v*sin(yaw)`. The yaw comes from the orientation quaternion in the pose message. Without this, forward would point the same way even after turning.
- **QoS.** MAVROS publishes the pose as best effort, so the pose subscription uses the sensor-data QoS profile. With the default one it never received anything.

The speeds, yaw rate, takeoff altitude and hold timeout are constants at the top of `teleop_node.py`, so they're easy to change.

## Setup
I tested this on Ubuntu 24.04 (WSL2 on Windows 11) with ROS 2 Jazzy, Gazebo Harmonic and ArduCopter 4.8. I installed everything by following the references from the task, in order:

1. ROS 2 Jazzy
2. Gazebo Harmonic
3. ROS 2 and Gazebo integration (`ros-jazzy-ros-gz`)
4. ArduPilot SITL and its dev environment
5. The `ardupilot_gazebo` plugin and Iris model
6. MAVROS (`ros-jazzy-mavros`, `ros-jazzy-mavros-extras`, and the `install_geographiclib_datasets.sh` script)

On WSL with Intel graphics, Gazebo showed a black screen at first, so I switched to software rendering:

```bash
echo "export LIBGL_ALWAYS_SOFTWARE=1" >> ~/.bashrc
```

```bash
cd ~/ros2_ws/src
git clone https://github.com/kavyasivakumar01/iris-keyboard-teleop-drone.git
cd ~/ros2_ws
colcon build --packages-select iris_keyboard_teleop
source install/setup.bash
```

## Running
Open four terminals and start them in this order, waiting for each one to finish loading.
**Terminal 1: Gazebo**
```bash
gz sim -v4 -r iris_runway.sdf
```
Wait until the runway and `iris_with_gimbal` show up.
**Terminal 2: ArduPilot SITL**
```bash
cd ~/ardupilot
Tools/autotest/sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON
```
Wait for `EKF3 IMU0 is using GPS`. Don't start it with `-w`, since that resets the frame parameters.
**Terminal 3: MAVROS**
```bash
ros2 launch mavros apm.launch fcu_url:=udp://:14550@
```
After about a minute, type this into the SITL terminal so it sends data to MAVROS. Without it, MAVROS stayed on `connected: false` for me.
```
output add 127.0.0.1:14550
```
**Terminal 4: Teleop node**
```bash
source ~/ros2_ws/install/setup.bash
ros2 run iris_keyboard_teleop teleop
```
The node waits for the connection, arms, takes off and climbs by itself. Once it prints `Keyboard active`, click the terminal and fly.
## Problems I ran into
- **Gazebo black screen.** Fixed with software rendering (see Setup). If it goes black again after a restart, old processes are usually still running. Close everything and run `wsl --shutdown` in PowerShell.
- **Slow simulation.** Software rendering runs Gazebo at only a few percent of real time, so the drone reacts slowly. It still does the right thing, just late.
- **`PreArm: Motors: Check frame class and type`.** I fixed it by running `param set FRAME_CLASS 1` and `param set FRAME_TYPE 1` in the SITL terminal, then restarting SITL.
- **Arming failed on the second flight.** The drone from the first flight was still in the air and armed. Land it first with the `LAND` mode and wait until it disarms.
- **`Warning, time moved backwards`** keeps scrolling in the SITL terminal. It's harmless.