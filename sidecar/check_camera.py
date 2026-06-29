"""Verify the Swift EP2M (or any UVC camera) shows up via OpenCV.

Run with `just check-camera`. Press q to quit.
"""

import sys

import cv2


def main() -> int:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: cv2.VideoCapture(0) could not open a camera.")
        print("Check the EP2M is plugged in, then verify Photo Booth sees it.")
        print("If Photo Booth sees it but OpenCV does not, grant your terminal")
        print("Camera access in System Settings > Privacy and Security > Camera.")
        return 1

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Camera opened at {width}x{height} @ {fps:.1f} fps")

    print("Showing live preview. Press q to quit.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("WARN: failed to read frame")
            break
        cv2.imshow("EP2M preview", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
