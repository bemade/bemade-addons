{
    "name": "Bemade LLM Backend",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "maintainers": ["dureposd"],
    "category": "Technical",
    "summary": "OpenAI-compatible LLM providers and named streams, with local-only "
    "gating, JSON-schema validated output and content-free call logs",
    "description": """
Bemade LLM Backend
==================

A small, dependency-free backend that lets other modules call a large language
model through any **OpenAI-compatible** ``/v1/chat/completions`` endpoint:
a local Ollama, vLLM or llama.cpp server, OpenRouter, OpenAI, and so on. It
uses plain ``requests``; no vendor SDK is needed.

Providers
---------
*Settings › Technical › LLM › Providers* (administrators only).

* ``base_url`` of the OpenAI-compatible API (e.g. ``http://localhost:11434/v1``
  for Ollama), an optional API key, optional extra HTTP headers (JSON), a
  timeout and the structured output mode the server supports.
* **On our infrastructure** (``is_local``): tick it only for a server you run
  yourself. Data sent to it never leaves your infrastructure.
* The API key can be overridden by the environment variable
  ``BEMADE_LLM_KEY_<CODE>`` (provider code in upper case), so keys can stay out
  of the database.

Streams
-------
*Settings › Technical › LLM › Streams*. A stream is a named use of a model,
identified by a ``code`` that calling modules look up::

    stream = env["bemade.llm.stream"].get("my_stream")
    result = stream.complete(system_prompt, data, schema)

* ``complete()`` sends the system prompt and the data (wrapped in delimiters,
  as data and never as instructions), asks for JSON that follows ``schema``
  (``response_format`` ``json_schema`` when the server supports it, plus a JSON
  instruction in every case), parses the answer and validates it against the
  schema. The validated object is returned.
* **Local only by default**: a stream with *Allow cloud providers* unticked
  refuses, before anything is sent, a provider that is not on our
  infrastructure.
* Errors are typed (``odoo.addons.bemade_llm.exceptions``):
  ``LlmNotConfigured``, ``LlmCloudRefused``, ``LlmTransportError``,
  ``LlmInvalidOutput``, all subclasses of ``BemadeLlmError``.

Pseudonymization (extension point)
----------------------------------
Before sending, ``complete()`` calls ``_pseudonymize(text)``, which returns the
text to send and a ``{placeholder: original}`` mapping; after validation it
calls ``_restore(obj, mapping)``, which puts the originals back in every string
of the result. Version 1 ships only the ``none`` pseudonymizer (no change). A
module adds one by extending the ``pseudonymizer`` selection and defining
``_pseudonymize_<value>(text)``.

Call log
--------
Each call writes one ``ir.logging`` line (*Settings › Technical › Logging*)
with the stream, provider, model, latency, token counts and status. Prompts
and responses are **never** logged.

Neutralized databases
---------------------
On a neutralized copy, API keys are blanked and providers that are not on our
infrastructure are archived.
""",
    "depends": ["base"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "views/bemade_llm_provider_views.xml",
        "views/bemade_llm_stream_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
