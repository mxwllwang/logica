#!/usr/bin/python
# Maxwell

"""Command-line tool to validate predicates from a syntax tree.

Args:
  JSON string from standard input

Output:
  Prints well formatted outputs for:
    Dict that maps from predicate name to list[calls]
    Validates each predicate in the Dict.
  
  Typical Usage:
  
  ./predicate logica_query.l
  (with predicate executable)
  
"""

import json
import sys
from typecheck import predicate_checker

# Read JSON String from standard input.
parsed_output = ""
for line in sys.stdin:
  parsed_output += line

predicate_map = predicate_checker.map_predicates(parsed_output)

# Format output.
print("\n" + str(len(predicate_map)) + " predicate(s) found\n")

# Format results of predicate_map
for predicate in predicate_map.keys():
  print("Predicate name:", predicate)
  print("Number of calls:", len(predicate_map.get(predicate)))
  print()
  i = 1
  for tup in predicate_map.get(predicate):
    print(" {}) Full_text: \"{}\"".format(i, tup[0]))
    print("  Fields:")
    for field in tup[1]:
      print("    field: {}, type: {}, value: {}".format(field.get('field'), field.get('type'), field.get('value')))
    i += 1
    print()
    
# Format results of validate_predicate
print("\nVerify_Predicates\n")

errors = predicate_checker.verify_predicates(parsed_output)
if len(errors[0]) == 0:
  print("\nNo Errors\n")
else:
  print("\nError Log\n")
  for error in errors[0]:
    for e in error[3]:
      print("Error in {}: {}".format(error[0], e))
    print("  Predicate reference call: {}".format(error[1]))
    print("  Predicate error call: {}".format(error[2]))
    print()