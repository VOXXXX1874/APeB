from typing import List

from pydantic import BaseModel, Field

class FilteredAction(BaseModel):
    reason: str = Field(
        ..., description="Why this action is important."
    )
    action_index: int = Field(
        ..., description="The index of the action in the history list."
    )

class Filtered(BaseModel):
    summary: str = Field(
        ..., description="A summary about this history chunk and its relationship with the query and candidates."
    )
    actions: List[FilteredAction] = Field(
        ...,
        description="The actions that is important according to current query and candidates.",
    )

class RewrittenQuery(BaseModel):
    user_intent: str = Field(
        ..., description="A basic summary of user persona from history, the target product of this user, and what feature this user will consider."
    )
    new_query: str = Field(
        ..., description="The rewritten query based on the analysis of user history."
    )

###

class SAReAct_ToolCall(BaseModel):
    reasoning: str = Field(
        ..., description="The reasoning behind, about how to determine target product, important entries, analysis, and how to build final query"
    )
    history_queries: List[str] = Field(
        ..., description="The queries that target the informations in user history."
    )
    candidate_queries: List[str] = Field(
        ..., description="The queries that target the informations in candidate products."
    )
    enough_information: bool = Field(
        ..., description="Whether current result contains enough information to answer the query."
    )
