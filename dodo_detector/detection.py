#!/usr/bin/env python

import cv2
import numpy as np
import tensorflow as tf

from abc import ABCMeta, abstractmethod
from object_detection.utils import label_map_util
from object_detection.utils import visualization_utils as vis_util
from imutils.video import WebcamVideoStream


class ObjectDetector(metaclass=ABCMeta):

    @abstractmethod
    def from_image(self, frame):
        """
        Detects objects in an image

        :param frame: a numpy.ndarray containing the image where objects will be detected
        :return: a tuple containing the image, with objects marked by rectangles,
        and a dictionary listing objects and their locations as `(ymin, xmin, ymax, xmax)`
        """
        pass

    def _detect_from_stream(self, get_frame, stream):
        """
        This internal method detects objects from images retrieved from a stream, given a method that extracts frames from this stream

        :param get_frame: a method that extracts frames from the stream
        :param stream: an object representing a stream of images
        """
        ret, frame = get_frame(stream)

        while ret:
            marked_frame, objects = self.from_image(frame)

            cv2.imshow("image", marked_frame)
            if cv2.waitKey(1) == 27:
                break  # ESC to quit

            ret, frame = get_frame(stream)

        cv2.destroyAllWindows()

    def from_camera(self, camera_id=0):
        """
        Detects objects in frames from a camera feed

        :param camera_id: the ID of the camera in the system
        """

        def get_frame(stream):
            frame = stream.read()
            ret = True
            return ret, frame

        stream = WebcamVideoStream(src=camera_id)

        stream.start()
        self._detect_from_stream(get_frame, stream)
        stream.stop()

    def from_video(self, filepath):
        """
        Detects objects in frames from a video file
        
        :param filepath: the path to the video file
        """

        def get_frame(stream):
            ret, frame = stream.read()
            return ret, frame

        stream = cv2.VideoCapture()
        stream.open(filename=filepath)

        self._detect_from_stream(get_frame, stream)


class KeypointObjectDetector(ObjectDetector):

    def __init__(self, database_path, detector_type='RootSIFT', matcher_type='BF', min_points=10):
        """
        Object detector based on keypoints. This class depends on OpenCV SIFT and SURF feature detection algorithms,
        as well as the brute-force and FLANN-based feature matchers.

        :param database_path: Path to the top-level directory containing subdirectories, each subdirectory named after a class of objects and containing images of that object.
        :param detector_type: either `SURF`, `SIFT` or `RootSIFT`
        :param matcher_type: either `BF` for brute-force matcher or `FLANN` for flann-based matcher
        :param min_points: minimum number of keypoints necessary for an object to be considered detected in an image
        """
        self.current_frame = 0
        self.detector_type = detector_type

        # get the directory where object textures are stored
        self.database_path = database_path

        if self.database_path[-1] != '/':
            self.database_path += '/'

        # minimum number of features for a KNN match to consider that an object has been found
        self.min_points = min_points

        # create the detector
        if self.detector_type in ['SIFT', 'RootSIFT']:
            self.detector = cv2.xfeatures2d.SIFT_create()
        elif self.detector_type == 'SURF':
            self.detector = cv2.xfeatures2d.SURF_create()

        # get which OpenCV feature matcher the user wants
        if matcher_type == 'BF':
            self.matcher = cv2.BFMatcher()
        elif matcher_type == 'FLANN':
            flann_index_kdtree = 0
            index_params = dict(algorithm=flann_index_kdtree, trees=5)
            search_params = dict(checks=50)  # or pass empty dictionary
            self.matcher = cv2.FlannBasedMatcher(index_params, search_params)

        # store object classes in a list
        # each directory in the object database corresponds to a class
        self.objects = [os.path.basename(d) for d in os.listdir(self.database_path)]

        # minimum object dimensions in pixels
        self.min_object_height = 10
        self.min_object_width = 10
        self.min_object_area = self.min_object_height * self.min_object_width

        # initialize the frame counter for each object class at 0
        self.object_counters = {}
        for ob in self.objects:
            self.object_counters[ob] = 0

        # load features for each texture and store the image,
        # its keypoints and corresponding descriptor
        self.object_features = {}

        for obj in self.objects:
            self.object_features[obj] = self._load_features(obj)

    def _load_features(self, object_name):
        """
        Given the name of an object class from the image database directory, this method iterates through all the images contained in that directory and extracts their keypoints and descriptors using the desired feature detector

        :param object_name: the name of an object class, whose image directory is contained inside the image database directory
        :return: a list of tuples, each tuple containing the processed image as a grayscale numpy.ndarray, its keypoints and desciptors
        """
        img_files = [
            join(self.database_path + object_name + '/', f) for f in listdir(self.database_path + object_name + '/')
            if isfile(join(self.database_path + object_name + '/', f))
        ]

        pbar = tqdm(desc=object_name, total=len(img_files))

        # extract the keypoints from all images in the database
        features = []
        for img_file in img_files:
            pbar.update()
            img = cv2.imread(img_file)

            # scaling_factor = 640 / img.shape[0]
            if img.shape[0] > 1000:
                img = cv2.resize(img, (0, 0), fx=0.3, fy=0.3)

            # find keypoints and descriptors with the selected feature detector
            keypoints, descriptors = self._detectAndCompute(img)

            features.append((img, keypoints, descriptors))

        return features

    def _detect_object(self, name, img_features, scene):
        """

        :param name: name of the object class
        :param img_features: a list of tuples, each tuple containing three elements: an image, its keypoints and its descriptors.
        :param scene: the image where the object `name` will be detected
        :return: a tuple containing two elements: the homography matrix and the coordinates of a rectangle containing the object in a list `[xmin, ymin, xmax, ymax]`
        """
        scene_kp, scene_descs = self._detectAndCompute(scene)

        for img_feature in img_features:
            obj_image, obj_keypoints, obj_descriptors = img_feature

            if obj_descriptors is not None and len(obj_descriptors) > 0 and scene_descs is not None and len(scene_descs) > 0:
                matches = self.matcher.knnMatch(obj_descriptors, scene_descs, k=2)

                # store all the good matches as per Lowe's ratio test
                good = []
                for match in matches:
                    if len(match) == 2:
                        m, n = match
                        if m.distance < 0.7 * n.distance:
                            good.append(m)

                # an object was detected
                if len(good) > self.min_points:
                    self.object_counters[name] += 1
                    source_points = np.float32([obj_keypoints[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                    destination_points = np.float32([scene_kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

                    M, mask = cv2.findHomography(source_points, destination_points, cv2.RANSAC, 5.0)

                    if M is None:
                        break

                    if (len(obj_image.shape) == 2):
                        h, w = obj_image.shape
                    else:
                        h, w, _ = obj_image.shape

                    pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)

                    # dst contains the coordinates of the vertices of the drawn rectangle
                    dst = np.int32(cv2.perspectiveTransform(pts, M))

                    # get the min and max x and y coordinates of the object
                    xmin = min(dst[x, 0][0] for x in range(4))
                    xmax = max(dst[x, 0][0] for x in range(4))
                    ymin = min(dst[x, 0][1] for x in range(4))
                    ymax = max(dst[x, 0][1] for x in range(4))

                    # transform homography into a simpler data structure
                    dst = np.array([point[0] for point in dst], dtype=np.int32)

                    # returns the homography and a rectangle containing the object
                    return dst, [xmin, ymin, xmax, ymax]

        return None, None

    def _detectAndCompute(self, image):
        """
        Detects keypoints and generates descriptors according to the desired algorithm
        
        :param image: a numpy.ndarray containing the image whose keypoints and descriptors will be processed
        :return: a tuple containing keypoints and descriptors
        """
        keypoints, descriptors = self.detector.detectAndCompute(image, None)
        if self.detector_type == 'RootSIFT' and len(keypoints) > 0:
            # Transforms SIFT descriptors into RootSIFT descriptors
            # apply the Hellinger kernel by first L1-normalizing
            # and taking the square-root
            eps = 1e-7
            descriptors /= (descriptors.sum(axis=1, keepdims=True) + eps)
            descriptors = np.sqrt(descriptors)

        return keypoints, descriptors

    def from_image(self, frame):
        self.current_frame += 1
        # Our operations on the frame come here

        detected_objects = {}

        for object_name in self.object_features:
            homography, rct = self._detect_object(object_name, self.object_features[object_name], frame)

            if rct is not None:
                xmin = rct[0]
                ymin = rct[1]
                xmax = rct[2]
                ymax = rct[3]

                if object_name not in detected_objects:
                    detected_objects[object_name] = []

                detected_objects[object_name].append((ymin, xmin, ymax, xmax))

                text_point = (homography[0][0], homography[1][1])
                homography = homography.reshape((-1, 1, 2))
                cv2.polylines(frame, [homography], True, (0, 255, 255), 10)

                cv2.putText(frame, object_name + ': ' + str(self.object_counters[object_name]), text_point, cv2.FONT_HERSHEY_COMPLEX_SMALL, 1.2, (0, 0, 0), 2)

        return frame, detected_objects


class SSDObjectDetector(ObjectDetector):

    def __init__(self, path_to_frozen_graph, path_to_labels, num_classes, confidence=.8):
        """
        Object detector powered by the TensorFlow Object Detection API.

        :param path_to_frozen_graph: path to the frozen inference graph file, a file with a `.pb` extension
        :param path_to_labels: path to the label map, a text file with the `.pbtxt` extension
        :param num_classes: number of object classes that will be detected
        :param confidence: a value between 0 and 1 representing the confidence level the network has in the detection to consider it an actual detection
        """

        if not 0 < confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

        # load (frozen) tensorflow model into memory
        self.detection_graph = tf.Graph()
        with self.detection_graph.as_default():
            od_graph_def = tf.GraphDef()
            with tf.gfile.GFile(path_to_frozen_graph, 'rb') as fid:
                serialized_graph = fid.read()
                od_graph_def.ParseFromString(serialized_graph)
                tf.import_graph_def(od_graph_def, name='')

        # Label maps map indices to category names, so that when our convolution
        # network predicts 5, we know that this corresponds to airplane.
        # Here we use internal utility functions, but anything that returns a
        # dictionary mapping integers to appropriate string labels would be fine
        label_map = label_map_util.load_labelmap(path_to_labels)
        self.categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=num_classes, use_display_name=True)
        self.category_index = label_map_util.create_category_index(self.categories)
        self.confidence = confidence

    def from_image(self, frame):
        # object recognition begins here
        height, width, z = frame.shape
        with self.detection_graph.as_default():
            with tf.Session(graph=self.detection_graph) as sess:
                image_np_expanded = np.expand_dims(frame, axis=0)
                image_tensor = self.detection_graph.get_tensor_by_name('image_tensor:0')
                # Each box represents a part of the image where a particular object was detected.
                boxes = self.detection_graph.get_tensor_by_name('detection_boxes:0')
                # Each score represent how level of confidence for each of the objects.
                # Score is shown on the result image, together with the class label.
                scores = self.detection_graph.get_tensor_by_name('detection_scores:0')
                classes = self.detection_graph.get_tensor_by_name('detection_classes:0')
                num_detections = self.detection_graph.get_tensor_by_name('num_detections:0')

                # Actual detection
                (boxes, scores, classes, num_detections) = sess.run([boxes, scores, classes, num_detections], feed_dict={image_tensor: image_np_expanded})

                detected_objects = {}

                # for each detection
                for x in range(scores.shape[0]):
                    # scores are given in descending order,
                    # so we only check the first one to see if it's
                    # higher than the minimum confidence
                    if scores[x, 0] < self.confidence:
                        break

                    class_name = self.categories[int(classes[x][0]) - 1]['name']  # nome do objeto dentro do dicionário de objetos

                    # get the detection box around the object
                    box_objects = boxes[x][0]
                    # positions of the box are between 0 and 1, relative to the size of the image
                    # we multiply them to get the box location in pixels
                    ymin = int(box_objects[0] * height)
                    xmin = int(box_objects[1] * width)
                    ymax = int(box_objects[2] * height)
                    xmax = int(box_objects[3] * width)

                    if class_name not in detected_objects:
                        detected_objects[class_name] = []

                    detected_objects[class_name].append((ymin, xmin, ymax, xmax))

                # Visualization of the results of a detection.
                vis_util.visualize_boxes_and_labels_on_image_array(
                    frame,
                    np.squeeze(boxes),
                    np.squeeze(classes).astype(np.int32),
                    np.squeeze(scores),
                    self.category_index,
                    use_normalized_coordinates=True,
                    line_thickness=8
                )
                ################################

                return frame, detected_objects