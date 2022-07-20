#!/usr/bin/python
# Maxwell

"""Command-line tool to convert syntax tree to predicate -> arg map.

Args:
  JSON string from standard input

Output:
  Dict from predicate -> list[arguments]
  
Run with: ./predicate logica_query.l
  
"""

import json
import sys

parsed_output = "" # json string
for line in sys.stdin:
  parsed_output += line

# List of dict describing parsed syntax tree.
syntax = json.loads(parsed_output) # Save json to dict

# Finds all predicate -> argument mappings contained in a dictionary
# and adds them to the specified predicate_map.
def find_predicate(root, p_list):
  if isinstance(root, list):
    for sub_dict in root:
      find_predicate(sub_dict, p_list)
    return
  elif not isinstance(root, dict):
    return
  
  # Find predicate and related arguments within JSON.
  find_p = root.get("predicate_name")
  find_r = root.get("record")
  if find_p is not None:
    if find_r is not None:
      p_list.append((find_p, find_r.get("field_value")))
    else:
      p_list.append((find_p, []))
    
  # Check subtrees for dictionaries.
  for key, sub_dict in root.items():
    find_predicate(sub_dict, p_list)
  
  return

predicate_list = []
find_predicate(syntax,  predicate_list)

# Format output.
print("\n" + str(len(predicate_list)) + " predicate(s) found\n")

for predicate, args in predicate_list:
  num_args = len(args)
  print(str(predicate) + " : "
        + str(num_args) + " argument(s)")
  print("\t\t" + str(args) + "\n")

