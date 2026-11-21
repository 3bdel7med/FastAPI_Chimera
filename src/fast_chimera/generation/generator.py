"""Responsibility: ask the LLM for ONE file, validate it, and ask again if it is not valid."""

from __future__ import annotations

from fast_chimera.core.exceptions import CodeValidationError
from fast_chimera.core.interfaces import LlmClient
from fast_chimera.generation.context import GenerationContext
from fast_chimera.generation.prompt_builder import FilePromptBuilder
from fast_chimera.generation.validators import ValidatorChain
from fast_chimera.llm.json_extraction import extract_code
from fast_chimera.planning.prompts.generation import generation_system_prompt, repair_system_prompt
from fast_chimera.planning.schemas import FileSpec


class FileGenerator:
    def __init__(
        self,
        llm: LlmClient,
        prompt_builder: FilePromptBuilder,
        validators: ValidatorChain,
        max_repair_attempts: int = 2,
    ) -> None:
        self._llm = llm
        self._prompts = prompt_builder
        self._validators = validators
        self._max_repairs = max_repair_attempts

    async def generate(self, spec: FileSpec, context: GenerationContext, current_code: str | None = None) -> str:
        """Returns code that passed validation, or raises CodeValidationError."""
        prompt = self._prompts.build_write_prompt(spec, context, current_code)
        answer = await self._llm.generate_text(prompt, generation_system_prompt(context.mode))
        code = extract_code(answer)

        for repair_round in range(self._max_repairs + 1):
            problems = self._validators.check(code, spec)
            if not problems:
                return code
            if repair_round == self._max_repairs:
                raise CodeValidationError(f"{spec.path} is still invalid after repairs: {'; '.join(problems)}")
            code = await self.repair(spec, context, code, "\n".join(problems))

        raise CodeValidationError(spec.path)  # unreachable; keeps type-checkers happy

    async def repair(self, spec: FileSpec, context: GenerationContext, code: str, problem: str) -> str:
        """Ask the model to fix `code` given a description (or traceback) of the problem."""
        prompt = self._prompts.build_repair_prompt(spec, context, code, problem)
        answer = await self._llm.generate_text(prompt, repair_system_prompt(context.mode))
        return extract_code(answer)
