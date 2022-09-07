#!/usr/bin/python
# Maxwell

""" Find predicates and generate list of errors from syntax tree.
"""

import json
import logging
import sys
import sqlite3

if '.' not in __package__:
  from common import logica_lib
else:
  from ..common import logica_lib

logging.basicConfig(
  level=logging.WARNING,
  format="%(asctime)s [%(levelname)s] %(message)s",
  datefmt="%m/%d/%Y %I:%M:%S %p",
  handlers=[
    logging.FileHandler("debug.log"),
    logging.StreamHandler(sys.stdout)
  ]
)

def verify_predicates(syntax_tree, p_reference={}, p_unchecked={}):
  """ Find predicate mismatches from a logica syntax tree.
  
  Args:
    syntax_tree: A json string representing logica syntax tree.
    p_reference: Dict from predicate name -> call that will serve as reference.
    p_unchecked: Dict from predicate name -> list of calls without a reference.

  Returns:
    A tuple comprising 3 elements (1, 2, 3):
    1) A list of all identified errors/mismatches in syntax tree. Errors will be
    in the format:
      (predicate_name, reference_call, error_call, error_text)
      where
      reference_call, error_call are in the format:
        (full_text, fields) where
          full_text: Full text from which the predicate call occured
          fields: Dict of field : type mappings.
            types are: string, number, boolean, null, list. TODO (verify these are the types)
    2) An updated dict from predicate name -> call that will serve as reference.
    3) An updated dict from predicate name -> list of calls without a reference.
    
  Modifies:
    p_reference may be updated? TODO
  
  """
  # Add predefined operators to p_reference
  num_operators = ['+', '-', '/', '*', '>','<','<=','>=','==']
  bool_operators = ['&&', '||']
  p_reference.update({operator:("Predefined Num Operator", [{'field': 'left', 'type': 'number'}, {'field': 'right', 'type': 'number'}]) for operator in num_operators})
  p_reference.update({operator:("Predefined Bool Operator", [{'field': 'left', 'type': 'boolean'}, {'field': 'right', 'type': 'boolean'}]) for operator in bool_operators})

  errors = []
  syntax = json.loads(syntax_tree) # Save json to dict.

  for entry in syntax:
    full_text = entry.get("full_text", "")
    head = entry.get("head", "")
    body = entry.get("body", "")
    
    p_list = []
    _find_predicate(head, p_list)
    _find_predicate(body, p_list)
    
    is_header = True # is_header holds only for the first predicate.
    
     # Find true type and add type to fields
    for (p_name, p_fields) in p_list:
      # for field in p_fields:
      #   field.update({'type' : _get_type(field)})
      
      call = (full_text, p_fields)
      
      # Imperative predicates are ignored.
      if p_name[0] == '@':
        logging.info("Ignoring imperative predicate {}".format(p_name))
        continue
      
      # Database Tables have their schema made into a header predicate first,
      # if reference does not yet exist. Then we can compare to the schema.
      if p_name[0] == '`' and p_name[-1] == '`' and p_name not in p_reference.keys():
        logging.info("Creating reference for database table {}".format(p_name))
        schema = _fetch_schema(p_name)
        # Create a independent header for tables from BigQuery
        reference_call = ("Fetch " + p_name, _fetch_schema(p_name))
        p_reference.update({p_name : reference_call})
        logging.debug(p_reference)
      
      # Check for duplicate field names.
      field_names = set()
      for p in p_fields:
        if p.get('field') in field_names:
          errors.append((p_name, None, call, ["Duplicate field {}".format(p.get('field'))]))
          break
        field_names.add(p.get('field'))

      if p_name in p_reference.keys():
        # If a reference already exists for this predicate.
        if is_header:
          # is_header is True for the first predicate.
          error = check_predicate(p_name, p_reference.get(p_name), call, True)
        else:
          error = check_predicate(p_name, p_reference.get(p_name), call)
        if error is not None:
          errors.append(error)
      else:
        # If no reference exists for this predicate.
        if is_header:
          # Create a reference for this predicate.
          p_reference.update({p_name : call})
          # Next, check p_unchecked for predicates that can now be compared.
          unchecked_predicates = p_unchecked.get(p_name, [])
          for unchecked_predicate in unchecked_predicates:
            error = check_predicate(p_name, unchecked_predicate, call)
            if error is not None:
              errors.append(error)
          p_unchecked.pop(p_name, None) # Remove from unchecked.
        else: # No reference exists yet.
          # Add predicate and call to list of uncheckable predicates.
          unchecked_calls = p_unchecked.get(p_name)
          if unchecked_calls is not None:
            unchecked_calls.append(call)
          else:
            p_unchecked.update({p_name : [call]})
      is_header = False
  
  return (errors, p_reference, p_unchecked)

# TODO: Complete method
def check_predicate(name, reference, call, is_header=False):
  """ Compare two calls to the same predicate and return an error if different.
  
  Args:
    name: Name of predicate.
    reference: The call to the predicate that will be treated as valid.
    call: The call to the predicate to be checked.
      reference, call are in the format:
        (full_text, fields) where
          full_text: Full text from which the predicate call occured
          fields: Dict of field : type mappings. # TODO: right now it's field:, type:, value:
    is_header: Set to True if predicate is a header predicate, e.g.
      Z where Z(a:, b:) :- X(a:), Y(b:);

  Returns:
    A tuple in the format (name, reference, call, errors)
      Where errors is a list of error messages.
    None if no error found.
    
  """
  # Fetch
  logging.info("Call to check_predicate on %s \nReference: %r\nCall: %r,\nis_header: %r",
              name, reference, call, is_header)
  
  errors = []
  # List of {field: value:} dicts in the reference and in the call.
  r_fields = reference[1]
  c_fields = call[1]
  

  # Handle Operators.
  operators = ['||', '&&', '->', '==', '<=', '>=', '<', '>', '!=',
      ' in ', '++?', '++', '+', '-', '*', '/', '%', '^', '!']
  unary_operators = ['-', '!'] # What to do with this?
  unsupported_operators = ['->', ' in ', '++?', '++', '%', '^', '!']
  
  if name in operators: # Predicate is an operator
    # TODO: Support operators
    if name in unsupported_operators:
      logging.warning("Unsupported Operator: {}".format(name))
      errors.append("Unsupported Operator: {}".format(name))
    else:
      for (r, c) in zip(r_fields, c_fields):
        if r.get('field') != c.get('field'):
            # TODO: Confirm that this is not possible
            errors.append("PROGRAM ERROR: Fields '{}' and '{}' are not the same for operator '{}'."
                        .format(r.get('field'), c.get('field'), name))
            logging.error("Unexpected operator field name")
            break
        # elif r.get('type') != c.get('type'):
        #     errors.append("Operator '{}' invalid for type '{}'."
        #                   .format(name, c.get('type')))
        #     break
  else: # Predicate is defined by the user
    # TODO: Improve error message reporting
    if is_header:
      # Header call fields must match reference exactly in order, number, and type.
      if len(r_fields) != len(c_fields):
        errors.append("Inconsistent number of predicate fields '{}' and '{}'."
                      .format(len(r_fields), len(c_fields)))
      
      for (r, c) in zip(r_fields, c_fields):
        if r.get('field') != c.get('field'):
          errors.append("Field names '{}' and '{}' do not match. Note that fields must be listed in a consistent order."
            .format(r.get('field'), c.get('field')))
        # elif r.get('type') != c.get('type'):
        #   errors.append("Fields '{}' and '{}' have inconsistent types '{}' and '{}'."
        #     .format(r.get('field'), c.get('field'), r.get('type'), c.get('type')))
        #   break

    # Body call field names must all exist within the reference.
    if len(r_fields) < len(c_fields):
      errors.append("Predicate {} has extraneous fields.".format(name))

    available_names = [r.get('field') for r in r_fields]
    for c in c_fields:
      field_name = c.get('field')
      if field_name not in available_names:
        errors.append("Unrecognized field name '{}'.".format(field_name))
      # TODO: Else if for if the types don't match. Are the types vawiables? idk.
    
  if len(errors) == 0:
    logging.info("No error found")
    return None
  else:
    logging.info("Error found")
    return (name, reference, call, errors)

#TODO: Enable BigQuery API from map_predicates.
# Then, enable bigquery API from verify_predicates.
def map_predicates(syntax_tree):
  """ Convert logica syntax tree into predicate -> calls map.
  
  Args:
    syntax_tree: A json string representing logica syntax tree.

  Returns:
     A dict mapping predicate_names to a list of calls.
     Each call is a tuple (full_text, fields) where
        full_text: Full text from which the predicate call occured.
        fields: List of field, where
          field: Dict {field:, value:, type:}
          # TODO: Make value obsolete
     
     # TODO: Is this an old format? I dont' think im currently doing this
     For instance:
        X(a: 1);
        X(a: 2);
        
        {X: [('X(a: 1)', {"a": value}),
          ('X(a: 2)', {"a": value_2})]}
        
      Where 
      value = {'expression': {'literal': {'the_number': {'number': '1'}}
  
  """
  syntax = json.loads(syntax_tree) # Save json to dict

  predicate_map = {}
  for entry in syntax:
    full_text = entry.get("full_text", "")
    
    head = entry.get("head", [])
    body = entry.get("body", [])
    p_list = []
    _find_predicate(head, p_list)
    _find_predicate(body, p_list)
    
    for (p_name, p_fields) in p_list:
      # Find true type and add type to fields
      # for field in p_fields:
      #   field.update({'type' : _get_type(field)})
      
      # Handle database tables from BigQuery
      if p_name[0] == '`' and p_name[-1] == '`':
        schema = _fetch_schema(p_name)
        # Create a independent header for tables from BigQuery
        _add_predicate(predicate_map, "Fetch " + p_name, p_name, schema)
        
      _add_predicate(predicate_map, full_text, p_name, p_fields)
  
  return predicate_map

def _fetch_schema(p_name):
  """ Fetch table schema from BigQuery table.
  Args:
    p_name: The bq path `project(optional).dataset.table_name` as provided to Logica
  
  Returns:
    A {field: field_name, type: data_type} dict representing specified table schema.
  """
  logging.info("Identified BigQuery table %s", p_name)
  p_components = p_name[1:-1].split('.')
  dataset = p_components[0] # dataset.tablename (within default project)
  if len(p_components) == 3: # If project is specified, i.e. project.dataset.tablename
    dataset = '`' + p_components[0] + '`.' + p_components[1]
  table_name = p_components[-1]
  # Query Information Schema Columns
  sql = ("SELECT COLUMN_NAME AS field, DATA_TYPE AS type \
  FROM {}.INFORMATION_SCHEMA.COLUMNS \
  WHERE TABLE_NAME = \"{}\"".format(dataset, table_name))
  logging.debug(sql)
  return json.loads(logica_lib.RunQuery(sql, output_format='json')) # Engine is bq by default
  

# _extract_predicate_to_list?
def _find_predicate(root, p_list):
  """ Recursively finds all predicates in the specified directory.
    
  Args:
    root: The json list or dict to search under.
    p_list: A list to append found predicates to.

  Returns:
    List of tuples (p_name, p_fields).
  """
  # If list, check all items.
  if isinstance(root, list):
    for sub_dict in root:
      _find_predicate(sub_dict, p_list)
    return
  elif not isinstance(root, dict):
    return
  # Root is type dict.
  # Find predicate and related arguments within JSON.
  find_p = root.get("predicate_name")
  find_r = root.get("record")
  if find_p is not None:
    if find_r is not None:
      p_list.append((find_p, find_r.get("field_value")))
    else:
      p_list.append((find_p, []))
    logging.info("Found predicate %s", find_p)

  # Check all subtrees for dictionaries.
  for key, sub_dict in root.items():
    _find_predicate(sub_dict, p_list)
  return

def _add_predicate(predicate_map, full_text, name, fields):
  """ Helper function that adds specified predicate call to map.
  
  If valid, adds a predicate call with the specified full_text,
  predicate name, and fields to the supplied predicate map.
  Otherwise this function does nothing.
  """
  if name == "": return
  predicate_calls = []
  if name in predicate_map.keys():
    predicate_calls = predicate_map.get(name)
  
  predicate_calls.append((full_text, fields))
  predicate_map.update({name: predicate_calls})
  return

# TODO: Main
def _get_type(field, variables):
  """ Parse syntax tree of a dict(field:, value:) for true type.
  
  Args:
    field: A dict containing field name and value tree.
    
  Returns:
    A string s describing the true type of the specified field:
      s in ["list","boolean","number","string","null"]
    None if type can't be handled.
  """
  value = field.get('value')
  if 'expression' not in value.keys():
    logging.error("No expression found in record")
    return None
  else:
    true_type = _ParseExpression(value.get('expression'))
    logging.info("Got type '%s' from field %r", true_type, field)
    return true_type

# When provided with the dict within {'expression': {_____}}
def _ParseExpression(e):
  """Reverse parsing logica.Expression."""
  exp_type = next(iter(e)) # Get type of expression.
  s = e.get(exp_type)
  logging.debug("Parsing '%s' in %s from expression %r", exp_type, s, e)
  if exp_type == 'combine':
    return _ParseCombine(s)
  elif exp_type == 'implication':
    return _ParseImplication(s)
  elif exp_type == 'literal':
    return _ParseLiteral(s)
  elif exp_type == 'variable':
    return _ParseVariable(s)
  elif exp_type == 'subscript':
    return _ParseSubscripts(s)
  # ParseNegationExpression returns an expression.
  else:
    return "UNCLEAR"

def _ParseLiteral(literal):
  """Parses a literal, returns final type.
  Args:
    literal: This part of the syntax tree {'literal': {literal}}
  """
  v = next(iter(literal))
  logging.debug("Parsing '%s' from literal %r", v, literal)
  if v == 'the_number':
    return 'number'
  elif v == 'the_string':
    return 'string'
  elif v == 'the_list':
    return 'list'
  elif v == 'the_bool':
    return 'bool'
  elif v == 'the_null':
    return 'null'
  elif v == 'the_predicate':
    return _ParsePredicate(literal.get(v)) # Call something!
  else:
    logging.warning("Literal did not match known possibilities.")
    return None
  
def _ParseVariable(s):
  """Parsing variable (does not return type str)
  Returns:
    A dict in the form {'variable' : var_name}.
  """
  logging.debug("Parsing variable %s from %r", s.get('var_name'), s)
  return {'variable' : s.get('var_name')}

def _ParsePredicate(s):
  """Parsing predicate (does not return type str)
  Returns:
    A dict in the form {'predicate' : p_name}.
  """
  return {'predicate' : s.get('predicate_name')}

# TODO
def _ParseCombine(s):
  """Parsing 'combine' expression."""
  logging.warning("Unhandled Expression")
  return "Unhandled Expression: Combine"

# TODO
def _ParseImplication(s):
  """Parses implication expression."""
  logging.warning("Unhandled Expression")
  return "Unhandled Expression: Implication"

def _ParseSubscript(s):
  """Parsing subscript expression."""
  logging.warning("Unhandled Expression")
  return "Unhandled Expression: Subscript"


