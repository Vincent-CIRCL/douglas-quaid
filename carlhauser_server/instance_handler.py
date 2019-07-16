#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging.config
# ==================== ------ STD LIBRARIES ------- ====================
import pathlib
import signal
import sys
import time
import traceback

import carlhauser_server.Configuration.database_conf as database_conf
import carlhauser_server.Configuration.distance_engine_conf as distance_engine_conf
import carlhauser_server.Configuration.feature_extractor_conf as feature_extractor_conf
import carlhauser_server.Configuration.webservice_conf as webservice_conf
import carlhauser_server.Singletons.database_start_stop as database_start_stop
import carlhauser_server.Singletons.singleton as template_singleton
import carlhauser_server.Singletons.worker_start_stop as worker_start_stop
from carlhauser_server.Singletons.worker_start_stop import WorkerTypes as workertype
# ==================== ------ PERSONAL LIBRARIES ------- ====================
from common.environment_variable import get_homedir, make_big_line

# ==================== ------ PREPARATION ------- ====================
# load the logging configuration
logconfig_path = (get_homedir() / pathlib.Path("carlhauser_server", "logging.ini")).resolve()


# ==================== ------ LAUNCHER ------- ====================
class Instance_Handler(metaclass=template_singleton.Singleton):
    """
    Handle a server instance
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Create configuration
        self.db_conf = database_conf.Default_database_conf()
        self.ws_conf = webservice_conf.Default_webservice_conf()
        self.fe_conf = feature_extractor_conf.Default_feature_extractor_conf()
        self.di_conf = distance_engine_conf.Default_distance_engine_conf()

        # Handlers
        self.db_startstop: database_start_stop.Database_StartStop = None
        self.worker_startstop: worker_start_stop.Worker_StartStop = None

    def launch(self, with_database: bool=True):
        """
        Launch a full server : Databases, workers (webservice to adder), wait for startup and check status of everything
        :type with_database: boolean to specify if database has to be launched. Useful for test purposes / if database is manually or externally launched.
        :return: Nothing
        """
        # Launch elements
        if with_database :
            self.start_database(wait=True)  # Wait for launch
        self.prevent_workers_shutdown()

        self.start_adder_workers()
        self.start_requester_workers()
        self.start_feature_workers()
        self.start_webservice()

        self.worker_startstop.wait_for_worker_startup()
        self.check_worker()

        print(make_big_line())
        print("Server is running and ready to accept queries (if no error shown upper than this line).")

    def stop(self):
        """
        Stop everything. Webservice, workers, and database
        :return: Nothing
        """

        print("Server is asked to stop, please wait until complete shutdown of the server by itself.")
        print(make_big_line())

        # Shutdown Flask worker
        self.stop_webservice()

        # Shutdown workers
        if not self.check_worker():
            self.shutdown_workers()
        else:
            self.logger.warning("All workers are already stopped.")

        # Shutdown database
        self.stop_database(wait=True)  # Wait for stop
        self.flush_workers()

        print(make_big_line())
        print("Server is stopped, correctly (if no error shown upper than this line).")


    # ==================== ------ DB ------- ====================
    def check_db_startstop(self):
        """
        Create a Singleton instance of DB handler if none is present
        :return: Nothing. Change the state of the instance handler object (itself)
        """
        if self.db_startstop is None:
            self.logger.info("DB Handler not present in core. Creation of DB handler singleton ...")
            self.db_startstop = database_start_stop.Database_StartStop(db_conf=self.db_conf)

    def check_worker_startstop(self):
        """
        Create a Singleton instance of DB handler if none is present
        :return: Nothing.
        """
        if self.worker_startstop is None:
            self.logger.info("Worker Handler not present in core. Creation of Worker handler singleton ...")
            self.worker_startstop = worker_start_stop.Worker_StartStop(db_conf=self.db_conf)

    def start_database(self, wait=False):
        """
        Start the database, with all redis and wait until running
        :param wait: bool, if True, will wait until db is started
        :return: Nothing
        """
        self.check_db_startstop()
        self.logger.info(f"Launching redis database (x2) ...")  # (cache and storage)
        self.db_startstop.launch_all_redis()

        if wait:
            if self.db_startstop.wait_until_all_redis_running():
                self.logger.info(f"Redis databases successfully launched (ping verified)")
            else:
                self.logger.critical(f"Redis databases are NOT launched (ping verified)")
                raise Exception("Impossible to connect to database : timeout while waiting for redis to run")

    def stop_database(self, wait=False):
        """
        Stop the database, with all redis, and wait until stopped
        :param wait: bool, if True, will wait until db is stopped
        :return: Nothing
        """
        self.check_db_startstop()
        self.logger.info(f"Stopping redis database (x2) ...")  # (cache and storage)
        self.db_startstop.stop_all_redis()

        if wait:
            if self.db_startstop.wait_until_all_redis_stopped():
                self.logger.info(f"Redis database successfully stopped (ping verified)")
            else:
                self.logger.critical(f"Redis database had NOT stopped (ping verified)")

    def flush_db(self):
        """
        Flush the database. Use at your own risks ! You will loose data !
        :return: Nothing
        """
        self.check_db_startstop()
        self.logger.info(f"Flushing redis database (x2) ...")  # (cache and storage)
        self.db_startstop.flush_all_redis()

    # ==================== ------ DB WORKERS ------- ====================

    def start_adder_workers(self):
        """
        Start adder workers (which add pictures from queue to the database)
        :return: Nothing
        """
        self.check_worker_startstop()
        self.logger.info(f"Launching to_add worker (x{self.db_conf.ADDER_WORKER_NB}) ...")
        self.worker_startstop.start_and_add_n_worker(worker_type=workertype.ADDER,
                                                     db_conf=self.db_conf, dist_conf=self.di_conf, fe_conf=self.fe_conf,
                                                     nb=self.db_conf.ADDER_WORKER_NB)

    def start_requester_workers(self):
        """
        Start requester workers (which request pictures from queue to the database)
        :return: Nothing
        """
        self.check_worker_startstop()
        self.logger.info(f"Launching to_request worker (x{self.db_conf.REQUESTER_WORKER_NB}) ...")
        self.worker_startstop.start_and_add_n_worker(worker_type=workertype.REQUESTER,
                                                     db_conf=self.db_conf, dist_conf=self.di_conf, fe_conf=self.fe_conf,
                                                     nb=self.db_conf.REQUESTER_WORKER_NB)

    # ==================== ------ FEATURE WORKERS ------- ====================

    def start_feature_workers(self):
        """
        Start feature workers (which compute features from pictures from queueto an other queue)
        :return: Nothing
        """
        self.check_worker_startstop()
        self.logger.info(f"Launching feature worker (x{self.fe_conf.FEATURE_ADDER_WORKER_NB} + x{self.fe_conf.FEATURE_REQUEST_WORKER_NB}) ...")
        self.worker_startstop.start_and_add_n_worker(worker_type=workertype.FEATURE_ADDER,
                                                     db_conf=self.db_conf, fe_conf=self.fe_conf,
                                                     nb=self.fe_conf.FEATURE_ADDER_WORKER_NB)
        self.worker_startstop.start_and_add_n_worker(worker_type=workertype.FEATURE_REQUESTER,
                                                     db_conf=self.db_conf, fe_conf=self.fe_conf,
                                                     nb=self.fe_conf.FEATURE_REQUEST_WORKER_NB)

    # ==================== ------ WEBSERVICE ------- ====================

    def start_webservice(self):
        """
        Start API webservice (Flask) to handle client requests
        :return: Nothing
        """
        self.check_worker_startstop()
        self.logger.info(f"Launching webservice ...")

        # Create configuration file
        self.ws_conf.CERT_FILE = self.ws_conf.CERT_FILE.resolve()
        self.ws_conf.KEY_FILE = self.ws_conf.KEY_FILE.resolve()
        self.worker_startstop.start_and_add_n_worker(worker_type=workertype.FLASK,
                                                     db_conf=self.db_conf, ws_conf=self.ws_conf,
                                                     nb=1)

    def stop_webservice(self):
        """
        Stop the webservice which handle clients requests
        :return: Nothing
        """
        self.check_worker_startstop()
        self.logger.info(f"Stopping webservice ...")
        self.worker_startstop.stop_list_worker(worker_type=workertype.FLASK)

    # ==================== ------ UTLITIES ON WORKERS ------- ====================

    def check_worker(self):
        """
        Check workers status
        :return: True if at least one worker alive, False otherwise
        """
        self.check_worker_startstop()
        self.logger.info(f"Checking for workers ...")
        return self.worker_startstop.is_there_alive_workers()

    def shutdown_workers(self):
        """
        Stop workers and wait for their shutdown
        :return: True if all workers are shutdown, False otherwise
        """
        self.check_worker_startstop()
        self.logger.info(f"Requesting workers to stop ...")
        self.db_startstop.request_workers_shutdown()
        return self.worker_startstop.wait_for_worker_shutdown()

    def prevent_workers_shutdown(self):
        """
        Remove the halt key from the database.
        Useful on launch to prevent worker to shutdown when they start from a recovered database.
        :return: Nothing
        """
        self.logger.info(f"Remove halt order to prevent workers to stop on launch...")
        self.db_startstop.prevent_workers_shutdown()

    def flush_workers(self):
        """
        Flush all workers. Kill them all and forget it. Goes away from the past.
        :return: True if all workers had been killed and removed from lists.
        """
        self.check_worker_startstop()
        self.logger.info(f"Requesting workers to stop ...")
        return self.worker_startstop.kill_and_flush_workers()


def exit_gracefully(signum, frame):
    """
    restore the original signal handler as otherwise evil things will happen
    in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
    signal.signal(signal.SIGINT, original_sigint) # TODO : To put back ?
    :param signum: ? Automatic
    :param frame:  ? Automatic
    :return: ? Automatic
    """

    try:
        stopper = Instance_Handler()
        print("Wait for the extinction ... ")
        stopper.stop()
        sys.exit(1)

    except KeyboardInterrupt:
        print("You should be nicer to carl-hauser.")
        sys.exit(1)

    # restore the exit gracefully handler here
    # signal.signal(signal.SIGINT, exit_gracefully) # TODO : To put back ?


if __name__ == '__main__':
    launcher = Instance_Handler()

    try:
        # Setting SIGINT handler
        # original_sigint = signal.getsignal(signal.SIGINT)  # Storing original
        signal.signal(signal.SIGINT, exit_gracefully)  # Setting custom
        launcher.launch()
        time.sleep(1)


        do_stop = False
        while not do_stop:
            print("Press any key to stop ... ")
            input()
            print("Are you sure you want to stop ? [yes/no] ")
            value = input()
            if value == "yes":
                do_stop = True

        launcher.stop()


    except KeyboardInterrupt:
        print('Interruption detected')
        try:
            print('Handling interruptions ...')
            launcher.stop()
            # TODO : Handle interrupt and shutdown, and clean ...
            sys.exit(0)
        except SystemExit:
            traceback.print_exc(file=sys.stdout)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        print(f'Critical problem during execution {e}')
        launcher.stop()
        sys.exit(0)
