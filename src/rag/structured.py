from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from src.rag.retriever import Resource, Retriever

POSSIBLE_RESOURCES = {
    "history": Resource(uri="history_actions_informations", title="Detail information of this user's history action",
                                              description=("There are two kinds of history action. "
                                                          "One is action involved video, where the information like ocr text, asr text, and product information (if any) are provided"
                                                          "The other is action involved product, where the information like product description, attributes, and action type are provided")),
    "candidates": Resource(uri="candidates_informations", title="Detail information of candidates",
                                              description=("Because user can order product from the shopping page or from video page. There are two kinds of candidates. "
                                                          "One is candidate from video, where the content like ocr text, asr text, and product information (if any) are provided"
                                                          "The other is candidate from shopping page, where the content like product description, attributes, and candidates type are provided")),
}

class StructuredBM25Retriever(Retriever):
    """
    StructuredBM25Retriever is a provider that retrieve structured resources.
    """

    def __init__(self, structured_resources: dict, task: str):
        self.data_resources = {}
        self.resources = []
        if task == "history":
            # create BM25 retrievers for history actions
            self.data_resources["history_actions_informations"] = BM25Retriever.from_documents(
                [Document(id=action[0], page_content=action[1]) for action in list(structured_resources["history_actions_informations"].items())]
            )
            self.data_resources["history_actions_informations"].k = 1
            self.resources.append(POSSIBLE_RESOURCES["history"])

        if task == "candidate":
            # Create BM25 retrievers for candidates
            self.data_resources["candidates_informations"] = BM25Retriever.from_documents(
                [Document(id=candidate[0], page_content=candidate[1]) for candidate in list(structured_resources["candidates_informations"].items())]
            )
            self.data_resources["candidates_informations"].k = 1
            self.resources.append(POSSIBLE_RESOURCES["candidates"])

    def query_relevant_documents(
        self, query: str, resources: list[Resource] = []
    ) -> list[Document]:
        """
        Query the retriever with a query and return the relevant documents.
        Args:
            query: The query to use for retrieval.
            resources: The resources to use for retrieval.
                Defaults to [].
                If empty, all resources will be used.
                If not empty, only the specified resources will be used.

        Returns:
            A list of relevant documents.
        """
        if not resources:
            resources = self.resources
        relevant_documents = []
        for resource in resources:
            relevant_documents.extend(self.data_resources[resource.uri].invoke(query))
        return relevant_documents

    def list_resources(self) -> list[Resource]:
        return self.resources
