"""Phrasing computed hazards with a language model, under the same copy rules as the templates.

The rules engine decides; the model only phrases. What keeps that true is the contract, not the
prompt: a narrated body may quote a figure only as a placeholder the client fills from
`HazardDef.facts`, so it cannot contain a digit at all, and `guard.py` drops any body that does,
that names a placeholder the hazard has no value for, or that uses a verdict word. A dropped body
is never repaired: the client shows its template instead.

Pure, like `hazards/`: the call to the model lives in `sources/narrator.py`.
"""
