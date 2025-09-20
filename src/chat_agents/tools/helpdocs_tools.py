from langchain_core.tools import tool


@tool(parse_docstring=True)
def search_helpdocs(query: str):
  """Search the helpdocs for padlet features related to the given query.

    Args:
        query (str): The search query,

    Returns:
        str: Text from the helpdocs related to the given query.
  """
  return "You can do it by contacting support."