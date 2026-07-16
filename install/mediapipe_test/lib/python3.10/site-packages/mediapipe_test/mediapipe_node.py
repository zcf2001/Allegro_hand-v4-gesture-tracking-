import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import mediapipe as mp 
from std_msgs.msg import Float32MultiArray
import cv2
import numpy as np

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
SAFETY_FACTOR = 0.8
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
        
        # 初始化 MediaPipe
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils          # 用于绘制
        self.mp_drawing_styles = mp.solutions.drawing_styles  # 绘制样式
        self.hands = self.mp_hands.Hands(
            static_image_mode=False, 
            max_num_hands=1, 
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5  # 添加跟踪置信度，提升流畅度
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
        
        # MediaPipe 处理
        results = self.hands.process(image_rgb)

        # 初始化 16 个关节角度
        joint_positions = [0.0] * 16

        # ===== 关键修改 1：无论是否检测到手，都绘制图像 =====
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # 绘制关节点和连线（使用官方样式，更美观）
                self.mp_drawing.draw_landmarks(
                    image,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style()
                )
                # 提取关节坐标
                for joint_idx in range(16):
                    if joint_idx < 12:  # 食指、中指、无名指
                        mp_idx = joint_idx + 5  # MediaPipe 对应的索引
                    else:  # 拇指
                        mp_idx = joint_idx - 7  # MediaPipe 对应的索引
                    landmark = hand_landmarks.landmark[mp_idx]
                    x, y, z = landmark.x, landmark.y, landmark.z
                    self.get_logger().info(f"Joint {joint_idx}: x={x:.3f}, y={y:.3f}, z={z:.3f}")
                
                #手腕
                p0 = np.array([hand_landmarks.landmark[0].x, hand_landmarks.landmark[0].y, hand_landmarks.landmark[0].z])
                
                #拇指(都是根部开始)
                p1 = np.array([hand_landmarks.landmark[1].x, hand_landmarks.landmark[1].y, hand_landmarks.landmark[1].z])
                p2 = np.array([hand_landmarks.landmark[2].x, hand_landmarks.landmark[2].y, hand_landmarks.landmark[2].z])
                p3 = np.array([hand_landmarks.landmark[3].x, hand_landmarks.landmark[3].y, hand_landmarks.landmark[3].z])
                p4 = np.array([hand_landmarks.landmark[4].x, hand_landmarks.landmark[4].y, hand_landmarks.landmark[4].z])
                
                # 食指
                p5 = np.array([hand_landmarks.landmark[5].x, hand_landmarks.landmark[5].y, hand_landmarks.landmark[5].z])
                p6 = np.array([hand_landmarks.landmark[6].x, hand_landmarks.landmark[6].y, hand_landmarks.landmark[6].z])
                p7 = np.array([hand_landmarks.landmark[7].x, hand_landmarks.landmark[7].y, hand_landmarks.landmark[7].z])
                p8 = np.array([hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y, hand_landmarks.landmark[8].z])

                # 中指
                p9 = np.array([hand_landmarks.landmark[9].x, hand_landmarks.landmark[9].y, hand_landmarks.landmark[9].z])
                p10 = np.array([hand_landmarks.landmark[10].x, hand_landmarks.landmark[10].y, hand_landmarks.landmark[10].z])
                p11 = np.array([hand_landmarks.landmark[11].x, hand_landmarks.landmark[11].y, hand_landmarks.landmark[11].z])
                p12 = np.array([hand_landmarks.landmark[12].x, hand_landmarks.landmark[12].y, hand_landmarks.landmark[12].z])

                # 无名指
                p13 = np.array([hand_landmarks.landmark[13].x, hand_landmarks.landmark[13].y, hand_landmarks.landmark[13].z])
                p14 = np.array([hand_landmarks.landmark[14].x, hand_landmarks.landmark[14].y, hand_landmarks.landmark[14].z])
                p15 = np.array([hand_landmarks.landmark[15].x, hand_landmarks.landmark[15].y, hand_landmarks.landmark[15].z])
                p16 = np.array([hand_landmarks.landmark[16].x, hand_landmarks.landmark[16].y, hand_landmarks.landmark[16].z])

                #小拇指不用，v4只有四根手指

                # 计算关节角度（先不管根部旋转）
                #食指
                v1 = p5 - p0
                v2 = p6 - p5
                v3 = p7 - p6
                v4 = p8 - p7

                self.angle_rad_index[0] = self.calculate_angle(v1, v2)
                self.angle_rad_index[1] = self.calculate_angle(v2, v3)
                self.angle_rad_index[2] = self.calculate_angle(v3, v4)
                
                
                #中指
                v5 = p9 - p0
                v6 = p10 - p9
                v7 = p11 - p10
                v8 = p12 - p11

                self.angle_rad_middle[0] = self.calculate_angle(v5, v6)
                self.angle_rad_middle[1] = self.calculate_angle(v6, v7)
                self.angle_rad_middle[2] = self.calculate_angle(v7, v8)


                #无名指
                v9 = p13 - p0
                v10 = p14 - p13
                v11 = p15 - p14
                v12 = p16 - p15

                self.angle_rad_pinky[0] = self.calculate_angle(v9, v10)
                self.angle_rad_pinky[1] = self.calculate_angle(v10, v11)
                self.angle_rad_pinky[2] = self.calculate_angle(v11, v12)

                #拇指
                v13 = p1 - p0
                v14 = p2 - p1
                v15 = p3 - p2
                v16 = p4 - p3
                
                self.angle_rad_thumb[0] = self.calculate_angle(v13, v14)
                self.angle_rad_thumb[1] = self.calculate_angle(v14, v15)
                self.angle_rad_thumb[2] = self.calculate_angle(v15, v16)


                #暂时忽略旋转关节：0, 4, 8, 12
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
                    
                    #self.get_logger().info(f"Calculated angle: {np.degrees(angle_rad),angle_rad} degrees")
                    # 映射到安全范围:第i个关节的最大和最小值,跳过旋转关节后还有12个关节
                    safe_min, safe_max = SAFE_LIMITS[i]
                    target_joint = float(np.clip(angle_rad, safe_min, safe_max))
                    self.get_logger().info(f"Target joint angle: {target_joint}")
                    joint_positions[i] = target_joint 


        # ===== 关键修改 2：显示窗口必须放在分支外面，保证每帧都刷新 =====
        cv2.imshow('MediaPipe Hand Tracking', image)
        
        # ===== 关键修改 3：必须调用 waitKey(1) 刷新窗口，否则卡死 =====
        # 同时检测按键 'q' 退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.get_logger().info('检测到 q 键，关闭节点...')
            rclpy.shutdown()

        # 发布 ROS 2 消息

        self.new_msg.position = joint_positions
        self.publisher_.publish(self.new_msg)
        


    def destroy_node(self):
        # ===== 关键修改 4：释放相机和销毁窗口，防止资源泄漏 =====
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


           
'''


        self.pub = self.create_publisher(JointState, '/allegroHand_0/joint_cmd', 10)
        for i in range(16):
            self.joint_name[i] = 'joint_' + str(i) + '.0'  

        self.position = 0.05             # 目标角度（弧度）
        self.create_timer(0.1, self.timer_cb)

    def timer_cb(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = [self.joint_name]
        msg.position = [self.position]
        self.pub.publish(msg)

'''