-- blank every LLM API key and archive providers outside our infrastructure
UPDATE bemade_llm_provider
   SET api_key = NULL;
UPDATE bemade_llm_provider
   SET active = false
 WHERE is_local IS NOT TRUE;
