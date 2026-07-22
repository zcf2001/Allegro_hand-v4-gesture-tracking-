import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import cv2
import numpy as np
from .single_hand_detector import SingleHandDetector

#sed -i '1s|.*|#!/home/fzc/ENTER/envs/hand/bin/python3|' install/mediapipe_test/lib/mediapipe_test/mediapipe_allegro_bridge 

# 来自 URDF 真实限位
JOINT_LIMITS = {
    # Index 食指
    0: (-0.57, 0.57),    1: (-0.296, 1.71),   2: (-0.274, 1.809),  3: (-0.327, 1.718),
    # Middle 中指
    4: (-0.57, 0.57),    5: (-0.296, 1.71),   6: (-0.274, 1.809),  7: (-0.327, 1.718),
    # Pinky 无名指
    8: (-0.57, 0.57),    9: (-0.296, 1.71),   10: (-0.274, 1.809), 11: (-0.327, 1.718),
    # Thumb 拇指（注意 joint_12 下限是正数）
    12: (0.3636, 1.4968), 13: (-0.205, 1.13), 14: (-0.2897, 1.633), 15: (-0.2622, 1.82),
}

# 手指编号速查
FINGER_JOINTS = {
    'index':  [0, 1, 2, 3],
    'middle': [4, 5, 6, 7],
    'pinky':  [8, 9, 10, 11],
    'thumb':  [12, 13, 14, 15],
}

# 安全使用范围（物理限位的 80%，留余量）
SAFETY_FACTOR = 0.9
SAFE_LIMITS = {}
for joint, (lo, hi) in JOINT_LIMITS.items():
    center = (lo + hi) / 2
    half_range = (hi - lo) / 2 * SAFETY_FACTOR
    SAFE_LIMITS[joint] = (center - half_range, center + half_range)

    
class SingleJointPub(Node):
    def __init__(self):
        super().__init__('mediapipe_allegro_bridge')
        
        self.publisher_ = self.create_publisher(JointState, '/allegroHand_0/joint_cmd', 10)
        self.subscriber_ = self.create_subscription(JointState, '/allegroHand_0/joint_states', self.joint_state_callback, 10)
        #订阅关节角度消息，并在回调中修改第 5 个关节的角度，然后发布新的消息
        
        # 初始化 SingleHandDetector（替代 MediaPipe 直接使用）
        self.hand_detector = SingleHandDetector(
            hand_type="Right",  # 或 "Left"，根据需要修改
            min_detection_confidence=0.8,
            min_tracking_confidence=0.8,
            selfie=True  # True 表示自拍视角（摄像头前置）
        )

        self.new_msg = JointState()

        self.angle_rad_index = [0.0] * 3  # 用于存储每个关节的角度（弧度）
        self.angle_rad_middle = [0.0] * 3
        self.angle_rad_pinky = [0.0] * 3
        self.angle_rad_thumb = [0.0] * 3

        # 启动定时器
        self.cap = cv2.VideoCapture(0)
        # 可选：设置分辨率，降低计算量
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.create_timer(0.03, self.timer_callback)  # 约 30fps
        self.get_logger().info('MediaPipe ROS2 Bridge 节点已启动！')

#订阅数据的时候调用,只获取关节角度数据，不发布
    def joint_state_callback(self, msg):
        # 这里可以处理接收到的关节状态消息
        self.get_logger().info(f"Received joint states: {msg.position}")
        #发布接收到的关节状态消息，并在此基础上修改第 5 个关节的角度
       
        self.new_msg.header.stamp = self.get_clock().now().to_msg()
        self.new_msg.name = msg.name
        self.new_msg.position = list(msg.position)
        self.get_logger().info(f"Position位置: {self.new_msg.position}")


#计算角度
    def calculate_angle(self, v1, v2):
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        # 防止除零
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
        return np.arccos(np.clip(dot_product / (norm_v1 * norm_v2), -1.0, 1.0))

#定时器调用
    def timer_callback(self):
        success, image = self.cap.read()
        if not success:
            self.get_logger().warn('相机读取失败')
            return

        # 镜像翻转（自拍视角）
        image = cv2.flip(image, 1)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # 使用 SingleHandDetector 进行检测
        num_box, joint_pos, keypoint_2d, mediapipe_wrist_rot = self.hand_detector.detect(image_rgb)

        # 初始化 16 个关节角度
        joint_positions = [0.0] * 16

        # ===== 检测到手的处理 =====
        if num_box > 0 and joint_pos is not None:
            # joint_pos 已经是3D坐标，形状为 (21, 3)
            # MediaPipe 关键点顺序：
            # 0=腕部, 1-4=拇指, 5-8=食指, 9-12=中指, 13-16=无名指, 17-20=小拇指
            
            # 绘制骨骼（使用 SingleHandDetector 的方法）
            self.hand_detector.draw_skeleton_on_image(image, keypoint_2d, style="white")
            
            # 从3D坐标计算关节角度
            # 腕部
            p0 = joint_pos[0]  # 腕部
            
            # 拇指（1-4）
            p1 = joint_pos[1]
            p2 = joint_pos[2]
            p3 = joint_pos[3]
            p4 = joint_pos[4]
            
            # 食指（5-8）
            p5 = joint_pos[5]
            p6 = joint_pos[6]
            p7 = joint_pos[7]
            p8 = joint_pos[8]

            # 中指（9-12）
            p9 = joint_pos[9]
            p10 = joint_pos[10]
            p11 = joint_pos[11]
            p12 = joint_pos[12]

            # 无名指（13-16）
            p13 = joint_pos[13]
            p14 = joint_pos[14]
            p15 = joint_pos[15]
            p16 = joint_pos[16]

            # 计算关节角度（相邻骨骼之间的夹角）
            # 食指
            v1 = p5 - p0
            v2 = p6 - p5
            v3 = p7 - p6
            v4 = p8 - p7

            self.angle_rad_index[0] = self.calculate_angle(v1, v2)
            self.angle_rad_index[1] = self.calculate_angle(v2, v3)
            self.angle_rad_index[2] = self.calculate_angle(v3, v4)
            
            # 中指
            v5 = p9 - p0
            v6 = p10 - p9
            v7 = p11 - p10
            v8 = p12 - p11

            self.angle_rad_middle[0] = self.calculate_angle(v5, v6)
            self.angle_rad_middle[1] = self.calculate_angle(v6, v7)
            self.angle_rad_middle[2] = self.calculate_angle(v7, v8)

            # 无名指
            v9 = p13 - p0
            v10 = p14 - p13
            v11 = p15 - p14
            v12 = p16 - p15

            self.angle_rad_pinky[0] = self.calculate_angle(v9, v10)
            self.angle_rad_pinky[1] = self.calculate_angle(v10, v11)
            self.angle_rad_pinky[2] = self.calculate_angle(v11, v12)

            # 拇指
            v13 = p1 - p0
            v14 = p2 - p1
            v15 = p3 - p2
            v16 = p4 - p3
            
            self.angle_rad_thumb[0] = self.calculate_angle(v13, v14)
            self.angle_rad_thumb[1] = self.calculate_angle(v14, v15)
            self.angle_rad_thumb[2] = self.calculate_angle(v15, v16)

            # 暂时忽略旋转关节：0, 4, 8, 12
            for i in range(16):
                if i % 4 == 0:
                    continue  # 跳过旋转关节
                if i < 4:
                    angle_rad = self.angle_rad_index[i % 4 - 1]
                elif i < 8:
                    angle_rad = self.angle_rad_middle[i % 4 - 1]
                elif i < 12:
                    angle_rad = self.angle_rad_pinky[i % 4 - 1]
                else:
                    angle_rad = self.angle_rad_thumb[i % 4 - 1]
                
                # 映射到安全范围
                safe_min, safe_max = SAFE_LIMITS[i]
                target_joint = float(np.clip(angle_rad, safe_min, safe_max))
                self.get_logger().info(f"Joint {i} angle: {target_joint:.4f} rad")
                joint_positions[i] = target_joint 


        # ===== 显示窗口（无论是否检测到手都显示）=====
        cv2.imshow('MediaPipe Hand Tracking', image)
        
        # ===== 刷新窗口，检测按键 'q' 退出 =====
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.get_logger().info('检测到 q 键，关闭节点...')
            rclpy.shutdown()

        # 发布 ROS 2 消息
        self.new_msg.position = joint_positions
        self.publisher_.publish(self.new_msg)
        


    def destroy_node(self):
        # 释放资源，防止资源泄漏
        self.get_logger().info('释放相机资源...')
        self.cap.release()
        cv2.destroyAllWindows()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = SingleJointPub()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('用户中断 (Ctrl+C)')
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()