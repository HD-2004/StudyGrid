"""HTTP layer. Route handlers, request and response shapes.

Contains no scheduling logic. Handlers validate input, call the scheduler, and
persist through the repository protocol.
"""
