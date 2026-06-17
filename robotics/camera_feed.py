import cv2

class CameraFeed:
    def __init__(self, cam_index=0):
        self.cam_index = cam_index
        self.capture = None

    def start_camera(self):
        print(f"[Camera] Starting camera at index {self.cam_index}...")
        self.capture = cv2.VideoCapture(self.cam_index)
        if not self.capture.isOpened():
            raise IOError(f"Cannot open camera index {self.cam_index}")

    def get_frame(self):
        if self.capture is None:
            raise ValueError("Camera not started. Call start_camera() first.")
        ret, frame = self.capture.read()
        if not ret:
            raise RuntimeError("Failed to grab frame from camera.")
        return frame

    def stop_camera(self):
        if self.capture:
            print("[Camera] Releasing camera...")
            self.capture.release()
            self.capture = None

    def show_camera_feed(self):
        self.start_camera()
        print("[Camera] Press 'q' to exit live feed.")
        while True:
            frame = self.get_frame()
            cv2.imshow("Live Camera Feed", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        self.stop_camera()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    cam = CameraFeed()
    cam.show_camera_feed()
