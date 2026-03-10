"""Pydantic models for rules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    rule_name: str = Field(..., max_length=200)
    category: str = Field(..., pattern="^(logistics|wip|equipment)$")
    subcategory: str | None = None
    query_template: str = Field(..., description="SQL with :bind_var")
    check_type: str = Field("threshold", pattern="^(threshold|delta|absence|llm)$")
    threshold_op: str = Field(">", pattern="^(>|<|>=|<=|=|!=)$")
    warning_value: float | None = None
    critical_value: float | None = None
    eval_interval: int = Field(300, ge=60)
    llm_enabled: bool = False
    llm_prompt: str | None = None
    enabled: bool = True


class RuleUpdate(BaseModel):
    rule_name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    query_template: str | None = None
    check_type: str | None = None
    threshold_op: str | None = None
    warning_value: float | None = None
    critical_value: float | None = None
    eval_interval: int | None = None
    llm_enabled: bool | None = None
    llm_prompt: str | None = None
    enabled: bool | None = None


class RuleResponse(BaseModel):
    rule_id: int
    rule_name: str
    category: str
    subcategory: str | None = None
    check_type: str
    threshold_op: str | None = None
    warning_value: float | None = None
    critical_value: float | None = None
    eval_interval: int = 300
    llm_enabled: bool = False
    enabled: bool = True
