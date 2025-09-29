import asyncio
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import json_repair
from langchain_core.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from tqdm.auto import tqdm

from config.prompts.eval import (
    COHERENCE,
    COVERAGE,
    LLM_JUROR_PROMPT,
    VALIDITY,
    VERIFIABILITY,
)
from llm_client import deploymentNames, deploymentNamesBedrock, yield_llm_client


@dataclass
class AnnotationTask:
    """Represents a single SQA annotation task."""

    id: str
    prompt: str
    criteria: str
    question: str
    data: str
    text: str


@dataclass
class JurorVote:
    """Represents a single juror's vote on an evaluation criterion."""

    juror_id: str
    criterion: str
    vote: str
    confidence: float
    reasoning: str


class LLMJuror:
    """Base class for LLM jurors."""

    def __init__(self, juror_id: str, deployment_name: str):
        self.juror_id = juror_id
        self.deployment_name = deployment_name

    async def annotate(self, task: AnnotationTask) -> Union[JurorVote, List[JurorVote]]:
        """Override this method for specific LLM implementations."""
        raise NotImplementedError


class OpenAIJuror(LLMJuror):
    """OpenAI GPT juror."""

    def __init__(self, juror_id: str, deployment_name: str):
        super().__init__(juror_id, deployment_name)
        self.client = yield_llm_client(
            deployment_name=deployment_name, aws_profile_name="lyk"
        ).bind(response_format={"type": "json_object"})

    async def annotate(self, task: AnnotationTask) -> List[JurorVote]:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(task.prompt),
                SystemMessagePromptTemplate.from_template(task.criteria),
                HumanMessagePromptTemplate.from_template(task.question),
                HumanMessagePromptTemplate.from_template(task.data),
                HumanMessagePromptTemplate.from_template(task.text),
            ]
        )
        messages = prompt.format_messages()
        response = self.client.invoke(messages).content
        result = json_repair.loads(response)
        return [
            JurorVote(
                juror_id=self.juror_id,
                vote=int(v["score"]),  # To prevent "5" vs. 5.
                confidence=v["confidence"],
                reasoning=v["explanation"],
                criterion=k,
            )
            for k, v in result.items()
        ]


class AnthropicJuror(LLMJuror):
    """Anthropic Claude juror."""

    def __init__(self, juror_id: str, deployment_name: str):
        super().__init__(juror_id, deployment_name)
        self.client = yield_llm_client(
            deployment_name=deployment_name,
            aws_profile_name="",
            aws_region_name="",
        )

    async def annotate(self, task: AnnotationTask) -> List[JurorVote]:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(task.prompt),
                SystemMessagePromptTemplate.from_template(task.criteria),
                HumanMessagePromptTemplate.from_template(task.question),
                HumanMessagePromptTemplate.from_template(task.data),
                HumanMessagePromptTemplate.from_template(task.text),
                # NOTE: Hack to get Claude to output consistent JSON, as it does not have a JSON mode; pre-empt an answer in the initial call.
                AIMessagePromptTemplate.from_template(
                    "Here is the JSON requested:\n{{"
                ),
            ]
        )
        messages = prompt.format_messages()
        response = self.client.invoke(messages).content
        result = json_repair.loads(
            "{" + response
        )  # Re-add the leading bracket that we pre-empted.
        return [
            JurorVote(
                juror_id=self.juror_id,
                vote=int(v["score"]),  # To prevent "5" vs. 5.
                confidence=v["confidence"],
                reasoning=v["explanation"],
                criterion=k,
            )
            for k, v in result.items()
        ]


class LLMJury:
    """Main jury system that coordinates multiple LLM jurors."""

    def __init__(self, jurors: List[LLMJuror]):
        self.jurors = jurors

    async def annotate_task(
        self, task: AnnotationTask
    ) -> Tuple[List[List[JurorVote]], Dict[str, Any]]:
        """Get annotations from all jurors for a single task."""
        # Get votes from all jurors concurrently.
        votes = await asyncio.gather(*[juror.annotate(task) for juror in self.jurors])
        # Calculate consensus.
        consensus_result = self._calculate_consensus(votes)
        # Return both raw annotations and processed consensus results for completeness.
        return (
            votes,
            dict(zip([v.criterion.title() for v in votes[0]], consensus_result)),
        )

    def _calculate_consensus(self, votes: List[List[JurorVote]]) -> Dict[str, Any]:
        """Calculate consensus from juror votes."""

        def process_set_of_votes(votes_: List[JurorVote]):
            shared_criterion = [v.criterion.lower() for v in votes_]
            # Sanity check that votes_ is correctly organized.
            assert all(x == shared_criterion[0] for x in shared_criterion), (
                f"Criterion mismatch between jurors: {str(shared_criterion)}"
            )
            # Simple majority voting.
            vote_counts = Counter(v.vote for v in votes_)
            majority_vote = vote_counts.most_common(1)[0][0]
            majority_count = vote_counts.most_common(1)[0][1]
            # Confidence-weighted voting.
            vote_weights = {}
            for vote in votes_:
                if vote.vote not in vote_weights:
                    vote_weights[vote.vote] = []
                vote_weights[vote.vote].append(vote.confidence)
            weighted_scores = {}
            for annotation, confidences in vote_weights.items():
                weighted_scores[annotation] = sum(confidences) / len(confidences)
            weighted_winner = max(weighted_scores, key=weighted_scores.get)
            # Agreement score.
            agreement_score = majority_count / len(votes_)
            # Use weighted result if confidence difference is significant.
            final_annotation = (
                weighted_winner
                if weighted_scores[weighted_winner]
                > weighted_scores.get(majority_vote, 0) + 0.1
                else majority_vote
            )
            return {
                "final_annotation": final_annotation,
                "agreement_score": agreement_score,
                "majority_vote": majority_vote,
                "weighted_vote": weighted_winner,
                "vote_distribution": dict(vote_counts),
                "confidence_scores": weighted_scores,
                "method": "weighted"
                if final_annotation == weighted_winner
                else "majority",
            }

        # Transpose JurorVotes by juror to get JurorVotes by criterion.
        return [process_set_of_votes(x) for x in list(map(list, zip(*votes)))]

    async def annotate_dataset(
        self, tasks: List[AnnotationTask]
    ) -> List[Dict[str, Any]]:
        """Annotate multiple tasks."""
        results = defaultdict(str)
        votes = defaultdict(str)
        pbar = tqdm(tasks, colour="green")
        for task in pbar:
            pbar.set_description(f"Processing task {task.id}")
            vote, result = await self.annotate_task(task)
            votes[task.id] = vote
            results[task.id] = result

        return votes, results


def load_tasks(dir: Path, verbose: bool = False):
    """Helper function for loading in the dataset."""
    tasks = []
    for file in tqdm(os.listdir(str(dir)), desc="Scanning directory", colour="green"):
        if file.endswith(".json"):
            json_ = json.load(open(str(dir) + "/" + file, "r"))["data"]
            tasks.append(
                AnnotationTask(
                    id=file,
                    prompt=LLM_JUROR_PROMPT,
                    criteria="\n\n".join(
                        [COVERAGE, COHERENCE, VERIFIABILITY, VALIDITY]
                    ),
                    question=json_["query"],
                    data=json_["input_to_writer"]
                    .replace("{", r"{{")
                    .replace("}", r"}}"),
                    text=json_["writer_response"],
                )
            )
            if verbose:
                tqdm.write(f"DONE {file}.")
    return tasks


async def main(in_dir: Path, out_dir: Path):
    # Create jurors.
    jurors = [
        OpenAIJuror("gpt1", deployment_name=deploymentNames.GPT_41_MINI.value),
        OpenAIJuror("gpt2", deployment_name=deploymentNames.GPT_4O_MINI.value),
        AnthropicJuror(
            "claude1", deployment_name=deploymentNamesBedrock.CLAUDE_35_HAIKU.value
        ),
        AnthropicJuror(
            "claude2", deployment_name=deploymentNamesBedrock.CLAUDE_35_SONNET.value
        ),
    ]
    # Create jury.
    jury = LLMJury(jurors)
    tasks = load_tasks(in_dir, verbose=True)
    # Run annotation.
    votes, results = await jury.annotate_dataset(tasks)
    # Save results.
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)
    for (file, res), v in tqdm(
        zip(results.items(), votes.values()),
        desc="Writing result files",
        colour="green",
    ):
        with open(str(out_dir / file), "w") as f:
            out = {"consensus": res, "votes": v}
            json.dump(out, f, indent=2, default=str)


if __name__ == "__main__":
    asyncio.run(
        main(
            in_dir=Path("sessions/..."),
            out_dir=Path("sessions/..."),
        )
    )
