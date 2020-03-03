Dodo's object detection package
===============================

This is a package that implements two types of object detection algorithms and provides them as Python classes, ready to be instantiated and used. The first algorithm uses a pipeline which consists of OpenCV keypoint detection and description algorithms, followed by feature matching and positioning using homography. Basically, `this tutorial <https://docs.opencv.org/3.4.1/d1/de0/tutorial_py_feature_homography.html>`__.

The second one uses any pre-trained convolutional network from the `TensorFlow Object Detection API <https://github.com/tensorflow/models/tree/master/research/object_detection>`__. Basically, `this tutorial <https://github.com/tensorflow/models/blob/master/research/object_detection/object_detection_tutorial.ipynb>`__.

As of now, the package works with both Python 2.7 and Python 3, but the tests work only on Python 3 because the code to download datasets is different between Python versions and I'm lazy.

Why
---

I have been working with object detection for quite some time now. After having to reimplement some detection algorithms, which are available online, but most times in a very convoluted way, I decided to create a Python package to make things easier not only for me, but for others.

Installation
------------

Besides the dependencies listed on ``setup.py``, the package also depends on the `OpenCV 3 nonfree/contrib packages <https://github.com/opencv/opencv_contrib>`__, which include the SURF [1]_ and SIFT [2]_ keypoint detection algorithms, as well as the `TensorFlow Object Detection API <https://github.com/tensorflow/models/tree/master/research/object_detection>`__. Follow their respective documentation pages to install them.

Since this package is not on PyPI, you can install it via ``pip`` like this:

.. code-block:: sh
    
    pip install git+https://github.com/douglasrizzo/dodo_detector.git

.. note::

    Please note that The TensorFlow Object Detection API does not yet support TensorFlow 2. This package has successfully been tested (up until 2020-21-02) with ``tensorflow>=1.13, <=1.15.2`` and ``tensorflow-gpu>=1.13, <=1.15.2``.
    
    The installation process detects if ``tensorflow-gpu`` is already installed. If not, it will install ``tensorflow>=1.13, <=1.15.2`` (without GPU support). If you want GPU support, make sure ``tensorflow`` is not installed and install ``tensorflow-gpu>=1.13, <=1.15.2`` yourself.

OpenCV is a hard dependency and is installed via the PyPI ``opencv-python`` package. If you already have OpenCV installed (*e.g.* from source), edit *setup.py* and remove the hard dependency before installing.

Usage
-----

The package has two types of detector, a keypoint-based detector and a detector based on pre-trained convolutional neural networks from the TensorFlow `model zoo <https://github.com/tensorflow/models/blob/master/research/object_detection/g3doc/detection_model_zoo.md>`__.

All detectors have a common interface, with three methods:

- ``from_camera`` takes a camera ID and uses OpenCV to read a frame stream, which is displayed on a separate window;
- ``from_video`` receives a video file and also displays the detection results on a window;
- ``from_image`` receives a single RGB image as a numpy array and returns a tuple containing an image with all the detected objects marked in it, and a dictionary containing object classes as keys and their detection information in tuples. Some classifiers return only bounding boxes, others return an additional confidence level. An example with one apple and two oranges detected in an image: ::

    {'person': [
        {'box': (204, 456, 377, 534), 'confidence': 0.9989906},
        {'box': (182, 283, 370, 383), 'confidence': 0.99848276},
        {'box': (181, 222, 368, 282), 'confidence': 0.9979938},
        {'box': (184, 37, 379, 109), 'confidence': 0.9938652},
        {'box': (169, 0, 371, 66), 'confidence': 0.98873794},
        {'box': (199, 397, 371, 440), 'confidence': 0.96926546},
        {'box': (197, 108, 365, 191), 'confidence': 0.96739936},
        {'box': (184, 363, 377, 414), 'confidence': 0.945458},
        {'box': (195, 144, 363, 195), 'confidence': 0.92953676}
    ]}

Keypoint-based detector
~~~~~~~~~~~~~~~~~~~~~~~

The keypoint-based object detector uses OpenCV 3 keypoint detection and description algorithms(namely, SURF [1]_, SIFT [2]_ and RootSIFT [3]_) to extract features from a database of images provided by the user. These features are then compared to features extracted from a target image, using feature matching algorithms also provided by OpenCV, in order to find the desired objects from the database in the target image.

Since OpenCV has no implementation of RootSIFT, I stole `this one <https://www.pyimagesearch.com/2015/04/13/implementing-rootsift-in-python-and-opencv/>`__.

Example on running a keypoint-based detector:

.. code-block:: python

    from dodo_detector.detection import KeypointObjectDetector
    detector = KeypointObjectDetector('/path/to/my/database_dir')
    marked_image, obj_dict = detector.from_image(im)

The database directory must have the following structure:

::

    database_dir
        beer_can
            img1.jpg
            img2.jpg
            img3.jpg
        milk_box
            hauihu.jpg
            172812.jpg
            you_require_additional_pylons.jpg
        chocolate_milk
            .
            .
        .
        .

Basically, the top-level directory will contain subdirectories. The name of each subdirectory is the class name the program will return during detection. Inside each subdirectory is a collection of image files, whose keypoints will be extracted by the ``KeypointObjectDetector`` during the object construction. The keypoints will then be kept in-memory while the object exists.

You can then use the methods provided by the detector to detect objects in your images, videos or camera feed.

Convolutional neural network detector [4]_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This detector uses TensorFlow Object Detection API. In order to use it, you must either train your own neural network using their API, or provide a trained network. I have a concise `tutorial <https://gist.github.com/douglasrizzo/c70e186678f126f1b9005ca83d8bd2ce>`__ on how to train a neural network, with other useful links.

The training procedure will give you the *frozen inference graph*, which is a ``.pb`` file; and a *label map*, which is a text file with extension ``.pbtxt`` containing the names of your object classes.

This type of detector must be pointed towards the paths for the frozen inference graph and label map. The number of classes can be explicitly passed, or else classes will be counted from the contents of the label map.

Example on running a single-shot detector:

.. code-block:: python

    from dodo_detector.detection import TFObjectDetector
    detector = TFObjectDetector('path/to/frozen/graph.pb', 'path/to/labels.pbtxt', 5)
    marked_image, obj_dict = detector.from_image(im)

Have fun!

.. rubric:: References

.. [1] H. Bay, A. Ess, T. Tuytelaars, and L. Van Gool, “Speeded-up robust features (SURF),” Computer vision and image understanding, vol. 110, no. 3, pp. 346–359, 2008.
.. [2] D. G. Lowe, “Object recognition from local scale-invariant features,” in Proceedings of the Seventh IEEE International Conference on Computer Vision, 1999, vol. 2, pp. 1150–1157.
.. [3] R. Arandjelović and A. Zisserman, “Three things everyone should know to improve object retrieval,” in 2012 IEEE Conference on Computer Vision and Pattern Recognition, 2012, pp. 2911–2918.
.. [4] W. Liu et al., “SSD: Single Shot MultiBox Detector,” arXiv:1512.02325 [cs], vol. 9905, pp. 21–37, 2016.
