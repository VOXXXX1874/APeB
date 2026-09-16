# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT
from typing import List

from pydantic import BaseModel, Field

class Product(BaseModel):
    product_title: str = Field(
        ..., description="The title of the product"
    )
    product_description: str = Field(
        ..., description="A detailed description of the product to make it more understandable"
    )
    product_recommendation_reason: List[str] = Field(
        default_factory=list,
        description="The reasons that this product is recommended to the user",
    )
    rank: int = Field(
        ..., description="The rank of the product in the recommendation, 1 being the most important"
    )
    index: int = Field(
        ..., description="The original index of the product in the candidates list"
    )


class Recommendation(BaseModel):
    title: str = Field(
        ..., description="Main topic of the recommendation"
    )
    summary: str = Field(
        ..., description="A summary that previews some important features for the recommendation"
    )
    products: List[Product] = Field(
        default_factory=list,
        description="The products that are recommended to the user, ranked by their importance",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "title": "Products Recommendation based on user query 'pero tumbler review'",
                    "summary": (
                        "User is searching for 'pero tumbler review', which means he/she is interested in pero tumbler. "
                        "For this query, the most important feature is Authenticity + official warranty (avoids fake goods, secures easy return)."
                        "Therefore, the most suitable product is TD Pero Tara Tumbler 798 ML. Other suitable products include ..."
                    ),
                    "products": [
                        {
                            "product_title": "TD Pero Tara Tumbler 798 ML",
                            "product_description": "A stainless steel tumbler with a 304 grade material, which is free of BPA and 304 grade. ",
                            "product_recommendation_reason": [
                                "Official Jordi Onsu, free charm, in-stock, viral trust—hits exclusivity sweet-spot.",
                            ],
                            "rank": 1,
                            "index": 16,
                        }
                    ]
                }
            ]
        }

class SimpleProduct(BaseModel):
    product_title: str = Field(
        ..., description="The title of the product"
    )
    rank: int = Field(
        ..., description="The rank of the product in the recommendation, 1 being the most important"
    )
    index: int = Field(
        ..., description="The original index of the product in the candidates list"
    )

class SimpleRecommendation(BaseModel):
    summary: str = Field(
        ..., description="A summary that previews some important features for the recommendation"
    )
    products: List[SimpleProduct] = Field(
        default_factory=list,
        description="The products that are recommended to the user, ranked by their importance",
    )
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "summary": (
                        "User is searching for 'pero tumbler review', which means he/she is interested in pero tumbler. "
                        "For this query, the most important feature is Authenticity + official warranty (avoids fake goods, secures easy return)."
                        "Other features include free charm, in-stock, viral trust—hits exclusivity sweet-spot ..."
                    ),
                    "products":[
                        {
                            "product_title": "TD Pero Tara Tumbler 798 ML",
                            "rank": 1,
                            "index": 16,
                        }
                    ]
                }
            ]
        }

class SupportingHistoryEntry(BaseModel):
    history_index: int = Field(
        ..., description="The index of the history entry that supports the recommendation of this product"
    )
    feature: str = Field(
        ..., description="The explicit feature that supports the recommendation of this product"
    )

class GroundedProduct(BaseModel):
    product_title: str = Field(
        ..., description="The title of the product"
    )
    product_description: str = Field(
        ..., description="A detailed description of the product to make it more understandable"
    )
    product_recommendation_reason: List[str] = Field(
        default_factory=list,
        description="The reasons that this product is recommended to the user",
    )
    rank: int = Field(
        ..., description="The rank of the product in the recommendation, 1 being the most important"
    )
    index: int = Field(
        ..., description="The original index of the product in the candidates list"
    )
    supporting_history_entries: List[SupportingHistoryEntry] = Field(
        default_factory=list,
        description="The history entries that support the recommendation of this product",
    )


class DetailedGroundedRecommendation(BaseModel):
    title: str = Field(
        ..., description="Main topic of the recommendation"
    )
    summary: str = Field(
        ..., description="A summary that previews some important features for the recommendation"
    )
    products: List[GroundedProduct] = Field(
        default_factory=list,
        description="The products that are recommended to the user, ranked by their importance",
    )

class SupportingHistoryFeature(BaseModel):
    summarized_feature: str = Field(
        ..., description="A summary that previews some important features from the history entries"
    )
    support_history_index: List[int] = Field(
        ..., description="List of history_index values supporting these features"
    )
    relevance_rank: int = Field(
        ..., description="Rank features by their direct textual alignment with query"
    )
    support_product: List[int] = Field(
        ..., description="List of candidate indices the summarized_feature supports"
    )


class StructuredRecommendation(BaseModel):
    target_product: str = Field(
        ..., description="What the user is literally trying to find"
    )
    concerned_features: str = Field(
        ..., description="A concise restatement of the top features the user is interested in"
    )
    products: List[Product] = Field(
        default_factory=list,
        description="The products that are recommended to the user, ranked by their suitability to the user's concerns",
    )
    historys: List[SupportingHistoryFeature] = Field(
        default_factory=list,
        description="The history entries and features that support the recommendation of this product",
    )