import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import mediapipe as mp 
from std_msgs.msg import Float32MultiArray
import cv2
import numpy as np

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

# ========== 新增：关键点索引到名称的映射，方便对照 ==========
LANDMARK_NAMES = {
    0:  "WRIST(手腕)",
    1:  "THUMB_CMC(拇指根)",
    2:  "THUMB_MCP",
    3:  "THUMB_IP",
    4:  "THUMB_TIP(拇指尖)",
    5:  "INDEX_MCP(食指根)",
    6:  "INDEX_PIP",
    7:  "INDEX_DIP",
    8:  "INDEX_TIP(食指尖)",
    9:  "MIDDLE_MCP(中指根)",
    10: "MIDDLE_PIP",
    11: "MIDDLE_DIP",
    12: "MIDDLE_TIP(中指尖)",
    13: "RING_MCP(无名指根)",
    14: "RING_PIP",
    15: "RING_DIP",
    16: "RING_TIP(无名指尖)",
    17: "PINKY_MCP(小指根)",
    18: "PINKY_PIP",
    19: "PINKY_DIP",
    20: "PINKY_TIP(小指尖)",
}


class SingleJointPub(Node):
    def __init__(self):
        super().__init__('point_visual')
        
        self.publisher_ = self.create_publisher(JointState, '/allegroHand_0/joint_cmd', 10)
        self.subscriber_ = self.create_subscription(JointState, '/allegroHand_0/joint_states', self.joint_state_callback, 10)
        
        # 初始化 MediaPipe
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.hands = self.mp_hands.Hands(
            static_image_mode=False, 
            max_num_hands=1, 
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        
        # 启动相机
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.create_timer(0.03, self.timer_callback)
        self.get_logger().info('MediaPipe ROS2 Bridge 节点已启动！')

    def joint_state_callback(self, msg):
        self.get_logger().info(f"Received joint states: {msg.position}")
        new_msg = JointState()
        new_msg.header.stamp = self.get_clock().now().to_msg()
        new_msg.name = msg.name
        new_msg.position = list(msg.position)
        self.get_logger().info(f"Position位置: {new_msg.position}")
        if len(new_msg.position) > 5:
            new_msg.position[5] = 0.5
        self.publisher_.publish(new_msg)

    def calculate_angle(self, v1, v2):
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
        return np.arccos(np.clip(dot_product / (norm_v1 * norm_v2), -1.0, 1.0))

    def draw_landmark_labels(self, image, hand_landmarks):
        """
        ========== 新增函数：在每个关键点旁边绘制索引编号 ==========
        """
        h, w, _ = image.shape
        for idx, landmark in enumerate(hand_landmarks.landmark):
            # MediaPipe 返回的是归一化坐标 (0.0~1.0)，需要转换为像素坐标
            cx, cy = int(landmark.x * w), int(landmark.y * h)
            
            # 绘制关键点编号（红色小圆点 + 白色文字）
            cv2.circle(image, (cx, cy), 4, (0, 0, 255), -1)  # 红色实心圆
            
            # 文字：显示索引号 + 简短名称
            label = f"p{idx}"
            # 文字位置稍微偏移，避免遮挡点
            text_x = cx + 8
            text_y = cy - 8
            
            # 黑色描边让文字更清晰
            cv2.putText(image, label, (text_x, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 3)  # 黑色粗描边
            cv2.putText(image, label, (text_x, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)  # 白色文字
            
            # 如果是你关心的几个点（p5,p6,p7,p8），用更大更亮的标记突出显示
            if idx in [5, 6, 7, 8]:
                cv2.circle(image, (cx, cy), 8, (0, 255, 255), 2)  # 黄色大圆圈
                # 在图像底部打印这些点的坐标信息
                self.get_logger().info(f"p{idx} ({LANDMARK_NAMES[idx]}): x={landmark.x:.3f}, y={landmark.y:.3f}, z={landmark.z:.3f}")

    def timer_callback(self):
        success, image = self.cap.read()
        if not success:
            self.get_logger().warn('相机读取失败')
            return

        image = cv2.flip(image, 1)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.hands.process(image_rgb)

        joint_positions = [0.0] * 16

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # 绘制 MediaPipe 默认的骨架连线
                self.mp_drawing.draw_landmarks(
                    image,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style()
                )
                
                # ========== 新增：绘制每个关键点的索引编号 ==========
                self.draw_landmark_labels(image, hand_landmarks)
                
                # 提取食指关键点计算角度
                p5 = np.array([hand_landmarks.landmark[5].x, hand_landmarks.landmark[5].y, hand_landmarks.landmark[5].z])
                p6 = np.array([hand_landmarks.landmark[6].x, hand_landmarks.landmark[6].y, hand_landmarks.landmark[6].z])
                p7 = np.array([hand_landmarks.landmark[7].x, hand_landmarks.landmark[7].y, hand_landmarks.landmark[7].z])
                p8 = np.array([hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y, hand_landmarks.landmark[8].z])
                
                v1 = p6 - p5
                v2 = p7 - p6
                angle_rad = self.calculate_angle(v1, v2)
                self.get_logger().info(f"Calculated angle: {np.degrees(angle_rad):.1f}° ({angle_rad:.3f} rad)")
                
                safe_min, safe_max = SAFE_LIMITS[5]
                target_joint = float(np.clip(angle_rad, safe_min, safe_max))
                self.get_logger().info(f"Target joint angle: {target_joint:.3f}")
                joint_positions[5] = target_joint

        # 在画面左上角添加图例说明
        legend_y = 30
        cv2.putText(image, "Landmark Labels: p0~p20", (10, legend_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(image, "Yellow circles: p5,p6,p7,p8 (index finger)", (10, legend_y + 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        cv2.imshow('MediaPipe Hand Tracking', image)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.get_logger().info('检测到 q 键，关闭节点...')
            rclpy.shutdown()

        # 发布 ROS 2 消息
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.position = joint_positions
        self.publisher_.publish(msg)

    def destroy_node(self):
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