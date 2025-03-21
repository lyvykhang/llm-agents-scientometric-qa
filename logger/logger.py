# Use: @logging_decorator(file_dumping=True, timing=True, printing=True, eval_track=True).

import datetime
import itertools
import json
import os
import sys
import time
from collections import defaultdict
from distutils.dir_util import remove_tree
from functools import wraps
from multiprocessing import current_process
from traceback import format_exc

import numpy as np
import uuid6
from flask import jsonify


SESSION_PATH: str = "sessions"
NEW_SESSION_PATH: str = f"{SESSION_PATH}/incomplete_session"
COMPLETE_SESSIONS_ARCHIVE = f"{SESSION_PATH}/completed_sessions"
FAILED_SESSIONS_ARCHIVE: str = f"{SESSION_PATH}/incomplete_sessions_archive"


def my_except_hook(exctype, value, traceback):
    sys.__excepthook__(exctype, value, traceback)


sys.excepthook = my_except_hook


def logging_decorator(
    printing: bool = False,
    timing: bool = False,
    file_dumping: bool = False,
    eval_track: bool = False,
):
    """Global logging decorator

    Args:
        printing (bool, optional): Print input args of function and output. Defaults to False.
        timing (bool, optional): Print runtime of fuction. Defaults to False.
        file_dumping (bool, optional): Dump error into file. Defaults to False.
        eval_track (bool, optional): Dump eval data into file. Defaults to False.
    Returns:
        _type_: Output of function
    """
    printing = False

    def function_caller(function):
        """The function caller

        Args:
            function (_type_): A function
        """

        def to_JSON(
            args, kwargs, function, time_start, e: Exception = "OK", res=None
        ) -> None:
            date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
            runtime = time.time() - time_start
            runtime = f"{np.round(runtime, 2)} seconds"
            save_path = f"{NEW_SESSION_PATH}/THREAD_{str(current_process().name)}"

            if not os.path.exists(save_path):
                os.makedirs(save_path, exist_ok=True)

            try:
                with open(
                    f"{save_path}/log_file_{date}_{str(uuid6.uuid8())}.json", "w"
                ) as f:
                    f.write(
                        json.dumps(
                            {
                                "Status": str(e),
                                "Function case": f"## DECORATOR running function -> {function.__name__} located in {function.__module__}",
                                # "args": args,
                                "kwargs": kwargs,
                                "res": str(res),
                                "function_ran": function.__name__,
                                "function_runtime": runtime,
                            },
                            indent=4,
                        )
                    )
            except Exception as ex:
                print(f"Failed to write log: {ex}")

        @wraps(function)
        def inner(*args, **kwargs):
            """logging functinality runner

            Returns:
                _type_: Output of function
            """
            error = 0
            print(
                "\n## DECORATOR running function -> ",
                function.__name__,
                "located in ",
                function.__module__,
            )
            if printing:
                print("Input args", args, kwargs)

            if timing:
                time_start = time.time()

            try:
                res = function(*args, **kwargs)
                if eval_track:
                    try:
                        if function.__name__ == "generate_summary":
                            if kwargs.get("use_streaming"):
                                res, it2 = itertools.tee(res, 2)
                                to_file = [
                                    jsonify(data)
                                    .get_data(as_text=False)
                                    .decode("utf-8")
                                    for data in it2
                                ]
                                to_file = "\n".join(
                                    [
                                        x.split('"data:')[1]
                                        .strip()
                                        .replace("{{newline}}", "")
                                        .replace(r"""\n""", "")
                                        .replace(r"""\\""", "")
                                        .replace('"', "")
                                        for x in to_file
                                        if '"data:' in x
                                    ]
                                )
                            else:
                                to_file = res
                        else:
                            to_file = res
                    except Exception as e:
                        to_file = res

                    to_JSON(str(args), str(kwargs), function, time_start, res=to_file)
                if printing:
                    print("Output: ", res)
            except Exception as e:
                error = 1
                print("Run into exception:", format_exc())
                print("Current arguments:", args)
                print("Current keyword arguments:", kwargs)

                if file_dumping:
                    to_JSON(args, kwargs, function, time_start, e=str(e))

            if timing:
                runtime = time.time() - time_start
                if runtime < 60:
                    print(f"Run took {np.round(runtime, 2)} seconds.")
                else:
                    print(f"Run took {np.round(runtime / 60, 2)} minutes.")
            print(
                "\n## DECORATOR finished running function -> ",
                function.__name__,
                "located in ",
                function.__module__,
            )
            print("\n#################\n")
            if not error:
                return res

        print(
            "## DECORATOR tracking function -> ",
            function.__name__,
            "located in ",
            function.__module__,
        )
        return inner

    return function_caller


def JSON_agg(origin: str, destination: str, runtime: int):
    """aggregates JSON session

    Args
        origin (str): origin folder
        destination (str): destination folder
        runtime (int): total run time in seconds
    """
    type_of = destination.split("/")[1].split("_")[0]
    session = defaultdict(int)
    if os.path.exists(origin):
        if len(os.listdir(origin)) > 0:
            for i, jason in enumerate(sorted(os.listdir(origin))):
                session[i] = json.loads(open(origin + "/" + jason).read())
                session[i]["file_name"] = jason
            session[i]["total_runtime"] = f"{str(runtime)} seconds"
            date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
            with open(
                f"{destination}/{type_of}_session_{date}_{str(uuid6.uuid8())}.json", "w"
            ) as f:
                f.write(json.dumps(session, indent=4))


def root_():
    os.makedirs(SESSION_PATH, exist_ok=True)
    os.makedirs(COMPLETE_SESSIONS_ARCHIVE, exist_ok=True)


def SESSION_STARTER():
    """START SESSION LOG TRACKING"""
    thread_id = f"THREAD_{str(current_process().name)}"
    print(thread_id)
    print("CHECKING SESSIONS FOLDERS ...")

    print("Yes made folder")
    os.makedirs(NEW_SESSION_PATH + "/" + thread_id, exist_ok=True)
    print(os.listdir(NEW_SESSION_PATH + "/" + thread_id))

    print(thread_id)
    if not os.path.exists(FAILED_SESSIONS_ARCHIVE):
        os.makedirs(FAILED_SESSIONS_ARCHIVE)
    else:
        print("FOUND INCOMPLETE SESSION ...")
        print("ARCHIVING ...")
        JSON_agg(NEW_SESSION_PATH + "/" + thread_id, FAILED_SESSIONS_ARCHIVE, 0)
        remove_tree(NEW_SESSION_PATH + "/" + thread_id)
        os.makedirs(NEW_SESSION_PATH + "/" + thread_id)
    print("DONE")


def SESSION_COMPILER(start_time: datetime):
    """ENDING LOG SESSION

    Args:
        start_time (datetime): time of start
    """
    thread_id = f"THREAD_{str(current_process().name)}"
    runtime = (datetime.datetime.now() - start_time).seconds
    print("ARCHIVING SESSION")
    JSON_agg(NEW_SESSION_PATH + "/" + thread_id, COMPLETE_SESSIONS_ARCHIVE, runtime)
    print("DONE")
    remove_tree(NEW_SESSION_PATH + "/" + thread_id)
