# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT
from typing import List

from pydantic import BaseModel, Field

class Feature(BaseModel):
    feature_short_description: str = Field(
        ..., description="A short description of the feature as its representative"
    )
    feature_detail_description: str = Field(
        ..., description="A detailed description of the feature to make it more understandable"
    )
    feature_sources: List[str] = Field(
        default_factory=list,
        description="The sources that this feature are derived from",
    )


class Report(BaseModel):
    title: str = Field(
        ..., description="Main topic of the report"
    )
    summary: str = Field(
        ..., description="A summary that previews the most important points of the report"
    )
    interested_features: List[Feature] = Field(
        default_factory=list,
        description="The features that user is interested in, ranked by their importance",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "title": "Report on the features that user will be interested in for current query.",
                    "summary": (
                        "User is searching for 'pero tumbler review', which means he/she is interested in pero tumbler. "
                        "For this query, the most important feature is the material safety & certification transparency (lack of 304/BPA-free mark)."
                        "Other features includes the durability, ease of use, and the overall quality of the product."
                    ),
                    "interested_features": [
                        {
                            "feature_short_description": "Material safety & certification transparency (lack of 304/BPA-free mark)",
                            "feature_detail_description": "user bought 304-grade bento box and explicitly BPA-free PP lunch boxes; she rejects items lacking visible safety marks. The Pero tumbler omits 304/316 or BPA-free claims, creating a credibility gap that must be resolved before purchase.",
                            "feature_sources": [
                                "1. play video with ecommerce intent; similar category; Product introducted in this video: Terlaris Bento Lunchbox Stainless Steel 304/ Rantang Kotak Makan 2 Susun Hl 465; Price: 11.75 usd",
                                "7. interact with video with ecommerce intent; similar category; Product introducted in this video: Portable Fruit Cup 30oz Large Capacity Dual Drinking Sports Water Bottle 304 Stainless Steel Insulated Cup; Price: 25.5 usd"
                            ],
                            "rank": 1,
                        }
                    ]
                }
            ]
        }
