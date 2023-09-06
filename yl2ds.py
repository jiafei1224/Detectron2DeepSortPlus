import argparse
import os
import time
from distutils.util import strtobool
import cv2
import numpy as np
from tqdm import tqdm

from yolov5_dt import Yolov5Detector
from sort import Sort
from deep_sort import DeepSort
import os  # Make sure you import os

from util import draw_bboxes, draw_detections

import cv2
import os




def main():
    args = get_parser().parse_args()

    # Create output directory for frames if it doesn't exist
    output_directory = "frames"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # Open the video file
    cap = cv2.VideoCapture(args.input)

    # Get video information
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    # Set the desired FPS
    desired_fps = 30

    # Calculate skip frames based on original and desired FPS
    skip_frames = max(1, int(fps / desired_fps))  # Ensure skip_frames is at least 1

    # Initialize frame counter
    frame_count = 0

    while True:
        ret, frame = cap.read()
        
        # Break the loop if the video has ended
        if not ret:
            break

        # Save only every nth frame based on desired FPS
        if frame_count % skip_frames == 0:
            frame_number = frame_count // skip_frames
            frame_filename = os.path.join(output_directory, f"{frame_number}.png")
            cv2.imwrite(frame_filename, frame)
            print(f"Saved {frame_filename}")

        frame_count += 1

    # Release video capture
    cap.release()

    print("Done!")

    if args.display:
        cv2.namedWindow("out_vid", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("out_vid", 1080, 1920)
    detector = Yolov5Detector(args.weights, args.img_size, args.conf_thres, args.nms_max_overlap, args.device, args.agnostic_nms)
    sort = Sort()
    deepsort = DeepSort(args.deepsort_checkpoint, nms_max_overlap=args.nms_max_overlap, use_cuda=bool(strtobool(args.use_cuda)))
    assert os.path.isfile(args.input), "Error: path error, input file not found"
    if args.out_vid:
        out_vid = cv2.VideoWriter(
            filename=args.out_vid,
            fourcc=cv2.VideoWriter_fourcc(*'MJPG'),
            fps=1.0,
            frameSize=(1080, 1920),
        )
    if args.out_txt:
        out_txt = open(args.out_txt, "w+")
    total_counter = [0]*1000
    inp_vid = cv2.VideoCapture(args.input)
    num_frames = int(inp_vid.get(cv2.CAP_PROP_FRAME_COUNT))
    for frameID in tqdm(range(num_frames)):
        ret, im = inp_vid.read()
        start = time.time()
        dets = detector.detect(im)
        if args.tracker == 'sort':
            if len(dets):
                dets = np.array(dets)
            else:
                dets = np.empty((0,5))
            outputs = sort.update(dets)
            outputs = np.array([element.clip(min=0) for element in outputs]).astype(int)
        else:
            if len(dets):
                ccwh_boxes = []
                for det in dets:
                    ccwh_boxes.append([(det[0]+det[2])/2, (det[1]+det[3])/2, det[2]-det[0], det[3]-det[1]])  
                ccwh_boxes = np.array(ccwh_boxes)
                confidences = np.ones(len(dets))
                outputs, __ = deepsort.update(ccwh_boxes, confidences, im)
            else:
                outputs = []
        current_counter = []
        if len(outputs):
            tlbr_boxes = outputs[:, :4]
            identities = current_counter = outputs[:, -1]
            ordered_identities = []
            for identity in identities:
                if not total_counter[identity]:
                    total_counter[identity] = max(total_counter) + 1
                ordered_identities.append(total_counter[identity])
            im = draw_bboxes(im, tlbr_boxes, ordered_identities)
            if args.out_txt:
                for i in range(len(ordered_identities)):
                    tlbr = tlbr_boxes[i]
                    center_x = (tlbr[0] + tlbr[2]) / 2  # Center x-coordinate
                    center_y = (tlbr[1] + tlbr[3]) / 2  # Center y-coordinate
                    line = [frameID+1, center_x, center_y]
                    out_txt.write(",".join(str(item) for item in line) + "\n")
                    
                    # top_left = (tlbr[0], tlbr[1])
                    # top_right = (tlbr[0], tlbr[3])
                    # bottom_left = (tlbr[2], tlbr[1])
                    # bottom_right = (tlbr[2], tlbr[3])
                    
                    # # Prepare the line to write in the output text file
                    # line = [
                    #     frameID+1, 
                    #     ordered_identities[i],
                    #     top_left[0], top_left[1],  # Top-left coordinates
                    #     top_right[0], top_right[1],  # Top-right coordinates
                    #     bottom_left[0], bottom_left[1],  # Bottom-left coordinates
                    #     bottom_right[0], bottom_right[1]  # Bottom-right coordinates
                    # ]
                    
                    # out_txt.write(",".join(str(item) for item in line) + "\n")


        end = time.time()
        im = cv2.putText(im, "Frame ID: "+str(frameID+1), (20,30), 0, 5e-3 * 200, (0,255,0), 2) 
        time_fps = "Time: {}s, fps: {}".format(round(end - start, 2), round(1 / (end - start), 2))            
        im = cv2.putText(im, time_fps,(20, 60), 0, 5e-3 * 200, (0,255,0), 3)      
        im = cv2.putText(im, args.weights + ' ' + args.tracker, (20, 90), 0, 5e-3*200, (0,255,0), 3) 
        im = cv2.putText(im, "Current Hand Counter: "+str(len(current_counter)),(20, 120), 0, 5e-3 * 200, (0,255,0), 2)
        im = cv2.putText(im, "Total Hand Counter: "+str(max(total_counter)), (20, 150), 0, 5e-3 * 200, (0,255,0), 2)
        if args.display:
            cv2.imshow("out_vid", im)
            cv2.waitKey(1)
        if args.out_vid:
            out_vid.write(im)
        frameID+=1

        # if not os.path.exists('saved_frames'):
        #     os.makedirs('saved_frames')

        # inp_vid = cv2.VideoCapture(args.input)
        # num_frames = int(inp_vid.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # for frameID in tqdm(range(num_frames)):
        #     ret, im = inp_vid.read()

        #     # ... (Your existing code for processing frames)

        #     # Save frame to the new folder
        #     frame_save_path = os.path.join('saved_frames', f'frame_{frameID + 1}.jpg')
        #     cv2.imwrite(frame_save_path, im)

def get_parser():
    parser = argparse.ArgumentParser(description="Yolov5 to (Deep)SORT demo")
    parser.add_argument("--input", 
         type=str,
         default='/media/data3/EgoCentric_Nafosted/non_skip/train/',
         help='path to input video', 
    )
    parser.add_argument("--tracker",
        type=str,
        default='sort',
        help='tracker type, sort or deepsort',
    )
    parser.add_argument("--deepsort_checkpoint",
        type=str,
        default="deep_sort/deep/checkpoint/ckpt.t7",
        help='Cosine metric learning model checkpoint',
    )
    parser.add_argument(
        "--max_dist",
        type=float, 
        default=0.5,
        help="Max cosine distance",
    )
    parser.add_argument("--nms_max_overlap",
        type=float,
        default=0.5,
        help='Non-max suppression threshold',
    )
    parser.add_argument('--weights', type=str, default='weights/best.pt', help='model.pt path')
    parser.add_argument(
        "--conf-thres",
        type=float,
        default=0.3,
        help="Minimum score for instance predictions to be shown",
    )
    parser.add_argument('--img-size', type=int, default=640, help='inference size (pixels)')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--device', default='cuda:0', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument(
        "--display",
        type=bool,
        default=True,
        help="Streaming frames to display",
    )
    parser.add_argument(
        "--out_vid", 
        type=str, 
        default="output_video.avi",
        help="Output video",
    )
    parser.add_argument(
        "--use_cuda", 
        type=str, 
        default="True",
        help="Use GPU if true, else use CPU only",
    )
    parser.add_argument(
        "--out_txt",
        type=str,
        default="output_pose.txt",
        help="Write tracking results in MOT16 format to file seqtxt2write. To evaluate using pymotmetrics",
    )
    parser.add_argument(
        "--opts",
        help="Modify config options using the command-line 'KEY VALUE' pairs",
        default=[],
        nargs=argparse.REMAINDER,
    )
    return parser

if __name__ == "__main__":
    main()
