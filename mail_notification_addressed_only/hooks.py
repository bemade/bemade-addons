DEFAULT_MODELS = ("sale.order", "project.task", "helpdesk.ticket", "account.move")


def post_init_hook(env):
    """List the default models once, on install only.

    Runs on install, never on update, so an administrator's removal of a
    default survives module upgrades. Models whose app is not installed are
    skipped.
    """
    Rule = env["mail.addressed.only.rule"].with_context(active_test=False)
    existing = Rule.search([]).model_id
    models_ = env["ir.model"].search(
        [("model", "in", list(DEFAULT_MODELS)), ("is_mail_thread", "=", True)]
    )
    Rule.create([{"model_id": m.id} for m in models_ - existing])
