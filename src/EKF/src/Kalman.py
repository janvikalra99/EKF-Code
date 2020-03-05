#!/usr/bin/env python
import math
import numpy as np
import Transformation as TF
import Triangulation
import sys
"""
Utility file which handles the prediction and update steps in a Kalman Filter.
"""

# Measurements are in meters.
L = 0.34 # Distance between two landmarks.

class Kalman:
	def __init__(self, x_initial, u_initial):
		# Kalman Filter Constants
		self.F = [[1, 0, 0, 0], 
			 	  [0, 1, 0, 0], 
			 	  [0, 0, 1, 0], 
			 	  [0, 0, 0, 0]]
		self.Q = np.eye(4) # Odometry covariance.
		self.R = np.eye(2) # RGB-D covariance.
		self.B = [[0, 0], # Initial B.
				  [0, 0],
				  [0, 1],
				  [1, 0]]
		self.x_t = x_initial
		P = 1
		self.P_pred = [[P, 0, 0, 0], 
			 	       [0, P, 0, 0], 
			 	       [0, 0, P, 0], 
			 	       [0, 0, 0, P]]
		self.P_t = [[P, 0, 0, 0], 
		 	        [0, P, 0, 0], 
		 	        [0, 0, P, 0], 
		 	        [0, 0, 0, P]] 
		self.linear_velocity = 0
		self.angular_velocity = 0

	""" Prediction in Kalman Filter: What is the current state based on the previous state?
	Call whenever there has been a change in robot pose.
	phi_t = orientation of robot at time t
    dt = change in time between t and t+1
	u_t = linear velocity at time t
	P_t = prediction at time t """
	def prediction(self, u_t, phi_t, dt):
		self.linear_velocity = u_t[0][0]
		self.angular_velocity = u_t[1][0]
		# Update 'B' matrix.
		self.B = [[-1.0 * math.cos(phi_t)*dt, 0],
		          [math.sin(phi_t)*dt, 0],
		          [0, dt],
		          [1, 0]]
		# Break down the linear velocity into it's x, y comments.
		y_linear_vel = self.linear_velocity * math.sin(phi_t)
		x_linear_vel = self.linear_velocity * math.cos(phi_t)
		# Jacobian linearization of 'F'.
		J_F = np.array([[1, 0, -1 * y_linear_vel * dt, math.cos(phi_t) * dt], 
		   			    [0, 1, x_linear_vel * dt, math.sin(phi_t) * dt],
					    [0, 0, 1, 0],
					    [0, 0, 0, 1]])

		self.x_t = np.dot(self.F, self.x_t) + np.dot(self.B, u_t)
		self.P_pred = np.dot(J_F, np.dot(self.P_t, J_F.transpose()).transpose()) + self.Q

	""" Update in Kalman Filter: Look at your input sensors, how much you trust each sensor, and how much you trust your overall state estimate.
	Call whenever there is change in sensed distance from the landmarks.
	x_p, y_p, phi = current robot x, y pose and orientation as measured by the wheel odometry sensor. 
	depth_landmark_1, depth_landmark_1 = sensed distance from robot to landmark 1 and 2 respectively."""
	def update(self, x_p, y_p, depth_landmark_1, depth_landmark_2, phi):
		# Transform frame of reference from robot to landmark 1. 
		x_r, y_r = TF.Pose_to_Landmark(x_p, y_p, phi)
		gamma = Triangulation.gamma_angle(depth_landmark_1, depth_landmark_2, L)
		# Jacobian linearization of 'H'.
		M = math.sqrt(x_r ** 2 + y_r ** 2)
		J_H = np.array(
			[[(x_r * math.cos(gamma)) / M, (y_r * math.cos(gamma)) / M, 0, 0], 
			 [(x_r * math.sin(gamma)) / M, (y_r * math.sin(gamma)) / M, 0, 0]])

		# Robot x, y pose as calculated by wheel odometry.
		z_a = np.array([[x_r, y_r]]).reshape(2, 1)
		# Robot x, y pose as observed by RDB-D by wheel odometry.
		z_t_1 = Triangulation.z_t(depth_landmark_2, depth_landmark_1, gamma).reshape(2, 1)

		error = np.subtract(z_a, z_t_1) / 5

		S = np.dot(J_H, np.dot(self.P_pred, J_H.transpose())) + self.R
		if self.is_invertible(S):
			Kalman_Gain = np.dot(self.P_t, np.dot(J_H.transpose(), np.linalg.inv(S)))
			self.x_t = self.x_t + np.dot(Kalman_Gain, error)
			self.P_t = np.subtract(self.P_t, np.dot(Kalman_Gain, np.dot(self.P_t, J_H.transpose()).transpose()))
		else:
			print("Matrix Singular; update failed.")

	# Checks whether matrix A is invertible. 
	def is_invertible(self, a):
		return a.shape[0] == a.shape[1] and np.linalg.matrix_rank(a) == a.shape[0]