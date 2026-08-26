import cv2
import numpy as np
import os

def create_test_video(output_path, duration_sec=10, fps=30, width=640, height=480):
    """Create a synthetic traffic-like video for pipeline testing."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    total_frames = duration_sec * fps
    
    for i in range(total_frames):
        # Create a road-like background
        frame = np.full((height, width, 3), 80, dtype=np.uint8)  # gray road
        
        # Draw lane markings
        for lane in range(1, 4):
            x = lane * (width // 4)
            cv2.line(frame, (x, 0), (x, height), (200, 200, 200), 2)
        
        # Draw moving "vehicles" (colored rectangles)
        np.random.seed(42)
        for v in range(5 + (i // 30) % 10):  # increasing congestion
            x = (v * 60 + i * 2) % (width - 40)
            y = 100 + (v % 3) * 120
            color = [(0,0,255), (0,255,0), (255,0,0), (0,255,255)][v % 4]
            cv2.rectangle(frame, (x, y), (x+40, y+30), color, -1)
        
        # Add timestamp
        cv2.putText(frame, f"Frame {i}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        
        out.write(frame)
    
    out.release()
    print(f"Test video created: {output_path}")
    print(f"  Duration: {duration_sec}s, Frames: {total_frames}")

if __name__ == '__main__':
    os.makedirs(r'C:\Pilli\trafficsense\outputs', exist_ok=True)
    create_test_video(r'C:\Pilli\trafficsense\outputs\test_traffic.mp4')
