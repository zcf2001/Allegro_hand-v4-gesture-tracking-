// Common allegro node code used by any node. Each node that implements an
// AllegroNode must define the computeDesiredTorque() method.

#include "allegro_node.h"
#include "allegro_hand_driver/AllegroHandDrv.h"

std::string jointNames[DOF_JOINTS] =
        {
                "joint_0.0", "joint_1.0", "joint_2.0", "joint_3.0",
                "joint_4.0", "joint_5.0", "joint_6.0", "joint_7.0",
                "joint_8.0", "joint_9.0", "joint_10.0", "joint_11.0",
                "joint_12.0", "joint_13.0", "joint_14.0", "joint_15.0"
        };

AllegroNode::AllegroNode(const std::string nodeName, bool sim /* = false */)
    : Node(nodeName)
{
  mutex = new boost::mutex();//创建互斥锁，用于保护共享资源的访问，确保线程安全。

  // Create arrays 16 long for each of the four joint state components
  current_joint_state.position.resize(DOF_JOINTS);//关节位置
  current_joint_state.velocity.resize(DOF_JOINTS);//关节速度
  current_joint_state.effort.resize(DOF_JOINTS);//关节力矩
  current_joint_state.name.resize(DOF_JOINTS); //关节名称

  // Initialize values: joint names should match URDF, desired torque and
  // velocity are both zero.
  for (int i = 0; i < DOF_JOINTS; i++) {
    current_joint_state.name[i] = jointNames[i];
    desired_torque[i] = 0.0;
    current_velocity[i] = 0.0;
    current_position_filtered[i] = 0.0;
    current_velocity_filtered[i] = 0.0;
  }


  // Get Allegro Hand information from parameter server
  std::string can_id, version;

  declare_parameter("~hand_info/which_hand", "");
  get_parameter("~hand_info/which_hand", whichHand);

  declare_parameter("~hand_info/version", "");
  get_parameter("~hand_info/version", version);

  declare_parameter("~comm/CAN_CH", "can0");
  get_parameter("~comm/CAN_CH", can_id);

  // Initialize CAN device
  canDevice = 0;
  if(!sim) {
    canDevice = new allegro::AllegroHandDrv();
    if (canDevice->init(can_id)) {
        usleep(3000);
    }
    else {
        delete canDevice;
        canDevice = 0;
    }
  }

  // Start ROS time
  tstart = get_clock()->now();

  // Advertise current joint state publisher and subscribe to desired joint
  // states.
  //创建发布器，发布当前关节状态。订阅器，接收期望的关节状态。
  joint_state_pub = this->create_publisher<sensor_msgs::msg::JointState>(JOINT_STATE_TOPIC, 3);
  joint_cmd_sub = this->create_subscription<sensor_msgs::msg::JointState>(DESIRED_STATE_TOPIC, 1, // queue size
                                                                          std::bind(&AllegroNode::desiredStateCallback, this, std::placeholders::_1));
}

AllegroNode::~AllegroNode() {
  if (canDevice) delete canDevice;
  delete mutex;
  rclcpp::shutdown();
}

void AllegroNode::desiredStateCallback(const sensor_msgs::msg::JointState &msg)
{
  mutex->lock();
  desired_joint_state = msg;
  mutex->unlock();
}

void AllegroNode::publishData() {
  // current position, velocity and effort (torque) published
  current_joint_state.header.stamp = tnow;//设置消息的时间戳为当前时间
  for (int i = 0; i < DOF_JOINTS; i++) {
    current_joint_state.position[i] = current_position_filtered[i];
    current_joint_state.velocity[i] = current_velocity_filtered[i];
    current_joint_state.effort[i] = desired_torque[i];
  }
  joint_state_pub->publish(current_joint_state);
}

void AllegroNode::updateController() {

  // Calculate loop time;
  tnow = get_clock()->now();//获取当前时间
  dt = 1e-9 * (tnow - tstart).nanoseconds();//计算时间间隔 dt，单位为秒。通过将当前时间减去上一次记录的时间，并将结果转换为纳秒，再乘以 1e-9 转换为秒。
  // dt = 1e-9 * (tnow - tstart).nsec;

  // When running gazebo, sometimes the loop gets called *too* often and dt will
  // be zero. Ensure nothing bad (like divide-by-zero) happens because of this.
  if(dt <= 0) {
    RCLCPP_DEBUG_STREAM_THROTTLE(rclcpp::get_logger("allegro_node"), *get_clock(), 1000, "AllegroNode::updateController dt is zero.");
    return;
  }

  tstart = tnow;


  if (canDevice)
  {
    // try to update joint positions through CAN comm:
    //尝试通过CAN通信更新关节位置。调用canDevice的readCANFrames()方法读取CAN帧，并将返回值赋给lEmergencyStop变量。
    lEmergencyStop = canDevice->readCANFrames();

    // check if all positions are updated:
    if (lEmergencyStop == 0 && canDevice->isJointInfoReady())
    {
      // back-up previous joint positions:
      for (int i = 0; i < DOF_JOINTS; i++) {
        previous_position[i] = current_position[i];
        previous_position_filtered[i] = current_position_filtered[i];
        previous_velocity[i] = current_velocity[i];
      }

      // update joint positions:
      //调用canDevice的getJointInfo()方法获取当前关节位置，并将结果存储在current_position数组中。
      canDevice->getJointInfo(current_position);

      // low-pass filtering:
      for (int i = 0; i < DOF_JOINTS; i++) {
        current_position_filtered[i] = (0.6 * current_position_filtered[i]) +
                                       (0.198 * previous_position[i]) +
                                       (0.198 * current_position[i]);
        current_velocity[i] =
                (current_position_filtered[i] - previous_position_filtered[i]) / dt;
        current_velocity_filtered[i] = (0.6 * current_velocity_filtered[i]) +
                                       (0.198 * previous_velocity[i]) +
                                       (0.198 * current_velocity[i]);
        current_velocity[i] = (current_position[i] - previous_position[i]) / dt;
      }

      // calculate control torque:
      computeDesiredTorque();

      // set & write torque to each joint:
      //给每个关节设置期望的扭矩，并通过CAN通信发送给Allegro手。
      //调用canDevice的setTorque()方法将desired_torque数组中的期望扭矩设置到Allegro手的关节上，然后调用writeJointTorque()方法将这些扭矩命令写入CAN总线。
      canDevice->setTorque(desired_torque);
      // writeJointTorque()方法返回一个整数值，表示写入操作的结果。将该返回值赋给lEmergencyStop变量，用于检查是否发生紧急停止。
      lEmergencyStop = canDevice->writeJointTorque();

      // reset joint position update flag:
      canDevice->resetJointInfoReady();

      // publish joint positions to ROS topic:
      publishData();

      frame++;
    }
  }

  if (lEmergencyStop < 0) {
    // Stop program when Allegro Hand is switched off
    RCLCPP_ERROR(rclcpp::get_logger("allegro_node"), "Allegro Hand Node is Shutting Down! (Emergency Stop)");
    rclcpp::shutdown();
  }
}

void AllegroNode::timerCallback() {
  updateController();
}
using namespace std::chrono_literals;

rclcpp::TimerBase::SharedPtr AllegroNode::startTimerCallback()
{
  auto timer = this->create_wall_timer(1ms, std::bind(&AllegroNode::timerCallback, this));
  return timer;
}
