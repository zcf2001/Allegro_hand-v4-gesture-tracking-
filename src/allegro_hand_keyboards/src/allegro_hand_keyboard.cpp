#include <rclcpp/rclcpp.hpp>
#include "std_msgs/msg/string.hpp"

#include <iostream>
#include <signal.h>
#include <termios.h>
#include <stdio.h>
#include <unistd.h>

#include "virtualkey_codes.h"

using namespace std;

#define DOF_JOINTS 16


class AHKeyboard : public rclcpp::Node
{
public:
  AHKeyboard();
  void keyLoop();
  void printUsage();

private:
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr cmd_pub_;
};

AHKeyboard::AHKeyboard() : Node("allegro_hand_keyboard")
{
  cmd_pub_ = this->create_publisher<std_msgs::msg::String>("allegroHand/lib_cmd", 10);
  //发布allegroHand/lib_cmd话题，消息类型为std_msgs::msg::String，队列长度为10
}


int kfd = 0;
struct termios cooked, raw;

void quit(int sig)
{
  tcsetattr(kfd, TCSANOW, &cooked);
  rclcpp::shutdown();
  exit(0);
}

//主函数，初始化ROS2节点，创建AHKeyboard对象，并设置SIGINT信号处理函数为quit，
//进入键盘事件循环，最后关闭ROS2节点并退出程序
int main(int argc, char** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<AHKeyboard>();//创建AHKeyboard对象，并将其作为共享指针返回

  signal(SIGINT, quit);
  //设置SIGINT信号处理函数为quit，当程序接收到SIGINT信号时，调用quit函数进行清理和退出

  node->keyLoop();
  rclcpp::shutdown();

  return 0;
}

void AHKeyboard::printUsage() {
  std::cout << std::endl;
  std::cout << " -----------------------------------------------------------------------------" << std::endl;
  std::cout << "  Use the keyboard to send Allegro Hand grasp & motion commands" << std::endl;
  std::cout << " -----------------------------------------------------------------------------" << std::endl;

  std::cout << "\tHome Pose:\t\t\t'H'" << std::endl;
  std::cout << "\tReady Pose:\t\t\t'R'" << std::endl;
  std::cout << "\tPinch (index+thumb):\t\t'P'" << std::endl;
  std::cout << "\tPinch (middle+thumb):\t\t'M'" << std::endl;
  std::cout << "\tGrasp (3 fingers):\t\t'G'" << std::endl;
  std::cout << "\tGrasp (4 fingers):\t\t'F'" << std::endl;
  std::cout << "\tGrasp (envelop):\t\t'E'" << std::endl;
  std::cout << "\tGravity compensation:\t\t'Z'" << std::endl;
  std::cout << "\tMotors Off (free motion):\t'O'" << std::endl;
  std::cout << "\tSave Current Pose:\t\t'S'" << std::endl;
  std::cout << "\tPD Control (last saved):\t'Space'" << std::endl;
  std::cout << "\tHelp (this message):\t\t'/ or ?'" << std::endl;
  std::cout << " -----------------------------------------------------------------------------" << std::endl;
  //std::cout << "  Note: Unless elsewhere implemented, these keyboard commands only work with " << std::endl;
  //std::cout << "  the 'allegro_hand_core_grasp' and 'allegro_hand_core_grasp_slp' packages." << std::endl;
  std::cout << "  Subscriber code for reading these messages is included in '~core_template'." << std::endl;
  std::cout << " -----------------------------------------------------------------------------\n" << std::endl;

}

void AHKeyboard::keyLoop()
{
  char c;
  bool dirty=false;

  // get the console in raw mode
  tcgetattr(kfd, &cooked);//获取当前终端的属性，并将其保存在cooked结构体中
  memcpy(&raw, &cooked, sizeof(struct termios));//将cooked结构体的内容复制到raw结构体中，准备修改raw结构体以设置终端为原始模式
  raw.c_lflag &=~ (ICANON | ECHO);
  // Setting a new line, then end of file
  raw.c_cc[VEOL] = 1;
  raw.c_cc[VEOF] = 2;
  tcsetattr(kfd, TCSANOW, &raw);//将修改后的raw结构体设置为当前终端的属性，使终端进入原始模式

  sleep(2);
  printUsage();

  for(;;)//进入一个无限循环，等待用户输入键盘事件
  {
    std_msgs::msg::String msg;//创建一个std_msgs::msg::String类型的消息对象，用于存储要发布的命令字符串
    std::stringstream ss;//创建一个字符串流对象，用于构建要发布的命令字符串

    // get the next event from the keyboard
    if(read(kfd, &c, 1) < 0)
    {
      perror("read():");
      exit(-1);
    }

    RCLCPP_DEBUG(this->get_logger(), "value: 0x%02X", c);
    switch(c)
    {
      case VK_SPACE:
        RCLCPP_DEBUG(this->get_logger(), "space bar: PD Control");
        ss << "pdControl";
        dirty = true;
        break;
      case KEYCODE_h:
        RCLCPP_DEBUG(this->get_logger(), "h_key: Home");
        ss << "home";
        dirty = true;
        break;
      case KEYCODE_r:
        RCLCPP_DEBUG(this->get_logger(), "r_key: Ready");
        ss << "ready";
        dirty = true;
        break;
      case KEYCODE_g:
        RCLCPP_DEBUG(this->get_logger(), "g_key: Grasp (3 finger)");
        ss << "grasp_3";
        dirty = true;
        break;
      case KEYCODE_f:
        RCLCPP_DEBUG(this->get_logger(), "f_key: Grasp (4 finger)");
        ss << "grasp_4";
        dirty = true;
        break;
      case KEYCODE_p:
        RCLCPP_DEBUG(this->get_logger(), "p_key: Pinch (index)");
        ss << "pinch_it";
        dirty = true;
        break;
      case KEYCODE_m:
        RCLCPP_DEBUG(this->get_logger(), "m_key: Pinch (middle)");
        ss << "pinch_mt";
        dirty = true;
        break;
      case KEYCODE_e:
        RCLCPP_DEBUG(this->get_logger(), "e_key: Envelop");
        ss << "envelop";
        dirty = true;
        break;
      case KEYCODE_z:
        RCLCPP_DEBUG(this->get_logger(), "z_key: Gravcomp");
        ss << "gravcomp";
        dirty = true;
        break;
      case KEYCODE_o:
        RCLCPP_DEBUG(this->get_logger(), "o_key: Servos Off");
        ss << "off";
        dirty = true;//设置dirty标志为true，表示有新的命令需要发布
        break;
      case KEYCODE_s:
        RCLCPP_DEBUG(this->get_logger(), "s_key: Save joint pos. for PD control");
        ss << "save";
        dirty = true;
        break;
      case KEYCODE_slash:
      case KEYCORD_question:
        printUsage();
        break;
    }

    if(dirty ==true)
    {
      msg.data = ss.str();
      RCLCPP_INFO(this->get_logger(), "%s", msg.data.c_str());
      cmd_pub_->publish(msg);
      rclcpp::spin_some(this->get_node_base_interface());//处理发布消息的回调函数，确保消息被正确发送.this指针指向当前节点对象，get_node_base_interface()返回节点的基本接口，用于处理回调函数
      dirty = false;
    }
  }

  return;
}
//ss->msg->cmd_pub   话题名称：allegroHand/lib_cmd，类型string    放要求指令