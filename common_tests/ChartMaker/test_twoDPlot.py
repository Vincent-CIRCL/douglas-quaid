# -*- coding: utf-8 -*-

import logging
import unittest

import common.ChartMaker.two_dimensions_plot as two_dimensions_plot
import common.Scalability_evaluator.scalability_evaluator as se
from common.Scalability_evaluator.scalability_evaluator import ScalabilityData, ComputationTime
from common.environment_variable import get_homedir


class TestClusterMatcher(unittest.TestCase):
    """Basic test cases."""

    def setUp(self):
        self.logger = logging.getLogger()
        # self.conf = .Default_configuration()
        self.test_path = get_homedir() / "datasets" / "douglas-quaid-tests" / "TwoDPlot"
        self.matrix_gen = two_dimensions_plot.TwoDimensionsPlot()

    def test_absolute_truth_and_meaning(self):
        self.assertTrue(True)

    def test_print_Scalability_Data(self):
        """

        +-----------------------------X------+         +--------------------------------+
    500 |                             X      |     1000|                               X|
        |                             X      |         |                            XXX |
        |                            XX      |         |                           XX   |
        |                            X       |         |                        XXX     |
     100|                           XX       |     100 |                     XXX        |
        |                          XX        |         |                 XXXX           |
        |                        XX          |   +-->  |              XXX               |
        |                     XXX            |         |            XX                  |
     20 |               XXXXXXX              |      10 |        XXXX                    |
        |        XXXXXXX                     |         |     XXX                        |
        |   XXXXXX                           |         |   XXX                          |
      0 | +X                                 |       0 |XXX                             |
        +------------------------------------+         +--------------------------------+
           0         10          30        50            0      10       100      1000

        :return:
        """
        t1 = ComputationTime()
        t1.adding_time = 100
        t1.nb_picture_added = 100
        t1.request_time = 10
        t1.nb_picture_requested = 10
        t1.iteration = 0

        t2 = ComputationTime()
        t2.adding_time = 1000
        t2.nb_picture_added = 500
        t2.request_time = 50
        t2.nb_picture_requested = 10
        t2.iteration = 2

        t3 = ComputationTime()
        t3.adding_time = 2300
        t3.nb_picture_added = 1000
        t3.request_time = 100
        t3.nb_picture_requested = 10
        t3.iteration = 3

        t4 = ComputationTime()
        t4.adding_time = 13000
        t4.nb_picture_added = 5000
        t4.request_time = 500
        t4.nb_picture_requested = 10
        t4.iteration = 4

        s = ScalabilityData()
        s.list_request_time = [t1, t2, t3, t4]

        tmp_se = se.ScalabilityEvaluator()
        tmp_se.print_data(s, self.test_path, file_name="scalability1.png")

        # TO VERIFY MANUALLY


if __name__ == '__main__':
    unittest.main()
