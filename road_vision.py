import numpy as np
import cv2
import math
import sys
import os
import lane_detection_v2 as ld
from cache import Cache
import matplotlib.path as mpltPath

# Used to flip the frame upside down
# Needed because dashboard cam is mounted upside down

class VPS(object):

	def __init__ (self, 
	CONF = 0.2,
	position_camera = False,
	record_raw = False,
	record_processed = False,
	show_visuals = True,
	calib = False, 
	invert = False, 
	lanes = True, 
	objects = True, 
	detect_all = False, 
	return_data = False,
	readout = True,
	cache_size = 5,
	size = (640,360), 
	region_of_interest = [[0.43,0.63],[0.57,0.63],[.95,.95],[.05,.95]]):

		self.CONF = CONF
		self.record_raw = record_raw
		self.record_processed = record_processed
		self.show_visuals = show_visuals
		self.invert = invert
		self.lanes = lanes
		self.objects = objects
		self.detect_all = detect_all
		self.return_data = return_data
		self.readout = readout
		self.size = size
		self.region_of_interest = region_of_interest


		self.roi_poly = mpltPath.Path(np.float32(region_of_interest)*np.float32(size))
		self.pipe_roi = [region_of_interest[0].copy(),region_of_interest[1].copy(),region_of_interest[3].copy(), region_of_interest[2].copy()]
		self.slope_left = abs(round(((1-region_of_interest[0][1])-(1-region_of_interest[3][1])) / (region_of_interest[0][0]-region_of_interest[3][0]),2))
		self.slope_right = abs(round(((1-region_of_interest[1][1])-(1-region_of_interest[2][1])) / (region_of_interest[1][0]-region_of_interest[2][0]),2))

		#print(slope_left, slope_right)

		self.lane_cache = Cache(max_size=cache_size)	
		# Cache stores previous lane curves so that when calculating new curves
		# if there is a large variance then it is reduced by taking the mean
		# with the cached lane curves

		# Calibrate the camera
		if calib:
			ld.calibrate(size=size)

		# Init some variables for object detection
		if objects:
			print("[INFO] loading model...")
			# Load the pretrained Object Detection Model
			self.net = cv2.dnn.readNetFromCaffe("mobilenetssd/MobileNetSSD_deploy.prototxt.txt", "mobilenetssd/MobileNetSSD_deploy.caffemodel")

			self.CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
						"bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
						"dog", "horse", "motorbike", "person", "pottedplant", "sheep",
						"sofa", "train", "tvmonitor"]

		if record_raw:
			if not os.path.exists('tests/'+sys.argv[1]):
				os.makedirs('tests/'+sys.argv[1])
			self.out_raw = cv2.VideoWriter('tests/{}/{}_raw.mp4'.format(sys.argv[1],sys.argv[1]),cv2.VideoWriter_fourcc(*'XVID'), 30, (1280,720))
		if record_processed:
			if not os.path.exists('tests/'+sys.argv[1]):
				os.makedirs('tests/'+sys.argv[1])
			self.out_processed = cv2.VideoWriter('tests/{}/{}_processed.mp4'.format(sys.argv[1],sys.argv[1]),cv2.VideoWriter_fourcc(*'XVID'), 30, (size[0]*2, size[1]))

		if position_camera:
			while(True):
				# ret = True/False if there is a next frame
				# frame = numpy pixel array
				ret, frame = cap.read()
				if not ret:
					break

				if invert:
					frame = invert_frame(frame)
				frame = cv2.resize(frame, size, interpolation = cv2.INTER_AREA)
				cv2.line(frame, (frame.shape[1]//2, 0), (frame.shape[1]//2, frame.shape[0]), (255,0,0), 1)
				cv2.polylines(frame, [np.array(np.float32(region_of_interest)*np.float32(size), np.int32)], True, (255,0,0), 1)

				cv2.imshow('Position Camera',frame)

				if cv2.waitKey(1) & 0xFF == ord('q'):
					cv2.destroyAllWindows()
					break

	def __del__(self):
		if self.record_raw:
			self.out_raw.release()
		if self.record_processed:
			self.out_processed.release()
		#print('VPS Destroyed')

	def invert_frame(self, frame):
		(H,W) = frame.shape[:2]
		center = (W/2, H/2)
		M = cv2.getRotationMatrix2D(center, 180, 1.0)
		frame = cv2.warpAffine(frame, M, (W,H))
		return frame

	def road_vision(self, frame):
		
		# ret = True/False if there is a next frame
		# frame = numpy pixel array

		if self.invert:
			frame = self.invert_frame(frame)

		if self.record_raw:
			self.out_raw.write(cv2.resize(frame, (1280, 720), interpolation = cv2.INTER_AREA))

		frame = cv2.resize(frame, self.size, interpolation = cv2.INTER_AREA)

		vehicles_detected = np.zeros_like(frame)
		
		pipe_roi_detected = [self.pipe_roi[0].copy(),self.pipe_roi[1].copy(),self.pipe_roi[2].copy(),self.pipe_roi[3].copy()]
		current_newY = self.pipe_roi[0][1]

		if self.objects:
			# Grab the frame dimensions and convert it to a blob
			(h, w) = frame.shape[:2]
			frame_slice = frame[math.ceil(h/2.5):h,:]
			(hh, ww) = frame_slice.shape[:2]
			vehicles_detected_slice = np.zeros_like(frame_slice)
			#cv2.imshow('slice', frame_slice)
			blob = cv2.dnn.blobFromImage(cv2.resize(frame_slice, (300, 300)), 0.007843, (300, 300), 127.5)

			# Pass the blob through the network and obtain the detections and predictions
			self.net.setInput(blob)
			detections = self.net.forward()

			# Loop over the detections
			for i in np.arange(0, detections.shape[2]):
				# Extract the confidence (i.e., probability) associated with the prediction
				confidence = detections[0, 0, i, 2]

				# Filter out weak detections by ensuring the `confidence` is
				# Greater than the minimum confidence
				if confidence > self.CONF:
					# Extract the index of the class label from the
					# `detections`, then compute the (x, y)-coordinates of
					# the bounding box for the object
					idx = int(detections[0, 0, i, 1])
					box = detections[0, 0, i, 3:7] * np.array([ww, hh, ww, hh])
					(startX, startY, endX, endY) = box.astype("int")

					# draw the prediction on the frame
					if self.detect_all or self.CLASSES[idx] in ['bus', 'car', 'motorbike']:

						W,H = (endX-startX), (endY-startY)

						object_dist = ((self.size[0] / W) * (self.size[1] / H))

						lane = ''

						midpoint = (startX+W//2,startY+H//2)

						color = (0,255,0)
						if self.roi_poly.contains_points([midpoint]) or (midpoint[0] > self.region_of_interest[0][0]*self.size[0] and midpoint[0] < self.region_of_interest[1][0]*self.size[0]):
							color = (255,0,0)
							lane = 'mine'
							if endY+math.ceil(h/2.5) > self.pipe_roi[0][1]*h:
								newY = round((endY+math.ceil(h/2.5)) / h,2)
								if newY > current_newY:
									current_newY = newY
									pipe_roi_detected[0][1] = newY
									pipe_roi_detected[0][0] = round((1-newY)/self.slope_left,2)
									pipe_roi_detected[1][1] = newY
									pipe_roi_detected[1][0] = 1-round((1-newY)/self.slope_right,2)

						elif midpoint[0] > self.size[0]//2:
							lane = 'right'
						else:
							lane = 'left'
						
						#cv2.rectangle(vehicles_detected_slice, midpoint, midpoint, color, 5)
						cv2.rectangle(vehicles_detected_slice, (startX, startY), (endX, endY), color, 2)
						cv2.rectangle(vehicles_detected_slice, (startX, startY), (endX, endY), [int(c * 0.4) for c in color], -1)

						#label_1 = '{} ({:.0f}%)'.format(self.CLASSES[idx], confidence*100)
						label_1 = '{}'.format(self.CLASSES[idx])
						#label_2 = 'dist: {:.0f}ft'.format(object_dist)
						label_3 = 'lane: {}'.format(lane)

						y = startY - 5 if startY - 5 > 5 else endY + 5

						cv2.putText(vehicles_detected_slice, label_1, (startX, y), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255,255,255), 1)
						#cv2.putText(vehicles_detected_slice, label_2, (startX, y+H+15), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255,255,255), 1)
						cv2.putText(vehicles_detected_slice, label_3, (startX, y+H+15), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255,255,255), 1)

			#cv2.imshow('slice', np.maximum(frame_slice, vehicles_detected_slice))
			vehicles_detected[math.ceil(h/2.5):h,:] = vehicles_detected_slice
		#cv2.imshow('vehicles', vehicles_detected)
		if self.lanes:
			rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
			detection_data = ld.vid_pipeline(rgb_frame, cache=self.lane_cache, roi=pipe_roi_detected, show=self.show_visuals)

			processed_frame = np.maximum(detection_data[0],vehicles_detected)
			lane_curve = detection_data[1]
			left_curve = detection_data[2]
			right_curve = detection_data[3]
			vehicle_offset = detection_data[4]
			turn = detection_data[5]
			visuals = detection_data[6]

			if self.readout:
				print('\rLeft Curve: {:6.0f}\tRight Curve: {:6.0f}\tCenter Curve: {:6.0f}\tVehicle Offset: {:.4f}\t\tTurn: {}\t\t\t'.format(left_curve, right_curve, lane_curve, vehicle_offset, turn), end='')

			processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_RGB2BGR)
			draw_region_of_interest = [pipe_roi_detected[0], pipe_roi_detected[1], pipe_roi_detected[3], pipe_roi_detected[2]]
			cv2.polylines(processed_frame, [np.array(np.float32(draw_region_of_interest)*np.float32(self.size), np.int32)], True, (255,0,0), 1)

		if self.show_visuals and self.lanes:
			processed_frame = np.concatenate((visuals, processed_frame), axis=1)

		if self.record_processed:
			self.out_processed.write(processed_frame)

		if not self.return_data:
			return processed_frame
		return (left_curve, right_curve, lane_curve, vehicle_offset, turn), processed_frame


if __name__ == "__main__":
	cap = cv2.VideoCapture('steering_wheel.png')
	#cap = cv2.VideoCapture(cv2.CAP_DSHOW)
	cap.set(3, 1280)
	cap.set(4, 720)

	vps = VPS()

	while True:
		ret, frame = cap.read()
		if not ret:
			break
		frame = vps.road_vision(frame)

		cv2.imshow('VPS', frame)
		if cv2.waitKey(1) & 0xFF == ord('q'):
			break

	cap.release()
	cv2.destroyAllWindows()
