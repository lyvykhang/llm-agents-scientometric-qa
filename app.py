from argparse import ArgumentParser
from datetime import datetime
from enum import Enum

import pipeline
import tools_api
from logger.logger import SESSION_COMPILER, SESSION_STARTER


class PipeTypes(Enum):
    naive = "naive"
    agentic_v3 = "agentic_v3"

    def __str__(self):
        return self.value


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--query", type=str, default="Which country published the most in 2022?"
    )
    parser.add_argument(
        "--method",
        type=PipeTypes,
        choices=list(PipeTypes),
        default=PipeTypes.agentic_v3,
    )
    args = parser.parse_args("")
    args.method = str(args.method)

    if args.method == "naive":
        pipe = pipeline.PipelineNaive(tool_module=tools_api, naive_query_building=True)
    elif args.method == "agentic_v3":
        pipe = pipeline.PipelineV3()

    SESSION_STARTER()
    time_start = datetime.now()
    pipe.run_conversation(query=args.query)
    SESSION_COMPILER(time_start)

    print("QUERY:", args.query)
    print(pipe)
