import logging

from odoo import api, models
from odoo.fields import Domain
from odoo.tools.sql import SQL, escape_psql, index_exists, make_index_name

_logger = logging.getLogger(__name__)

# Name of the full-text search configuration and of the pass-through
# dictionary created by Knowledge, and of the filtering dictionary provided by
# the PostgreSQL ``unaccent`` extension.
TS_CONFIG = "knowledge_config"
TS_DICTIONARY = "knowledge_dictionary"
UNACCENT_DICTIONARY = "unaccent"


class KnowledgeArticle(models.Model):
    _inherit = "knowledge.article"

    def init(self):
        res = super().init()
        self._bemade_unaccent_body_search(enable=True)
        return res

    # ------------------------------------------------------------
    # Article text: unaccent the full-text search configuration
    # ------------------------------------------------------------

    @api.model
    def _bemade_ts_dictionary(self, name):
        """(oid, schema) of the text search dictionary ``name``, or None.

        The dictionary of the current schema wins; otherwise the one of any
        schema, since the ``unaccent`` extension is often installed in a
        schema of its own (with an immutable ``unaccent()`` wrapper in the
        current one for Odoo's indexes).
        """
        self.env.cr.execute(
            SQL(
                """
                SELECT dict.oid::bigint, nsp.nspname
                  FROM pg_ts_dict dict
                  JOIN pg_namespace nsp ON nsp.oid = dict.dictnamespace
                 WHERE dict.dictname = %s
              ORDER BY nsp.nspname = current_schema() DESC, dict.oid
                 LIMIT 1
                """,
                name,
            )
        )
        return self.env.cr.fetchone()

    @api.model
    def _bemade_ts_config_mapping(self):
        """{token type alias: [dictionary oids in mapping order]} of the
        Knowledge text search configuration, or None when it does not exist."""
        cr = self.env.cr
        cr.execute(
            SQL(
                """
                SELECT oid::bigint
                  FROM pg_ts_config
                 WHERE cfgname = %s
                   AND cfgnamespace = current_schema::regnamespace
                """,
                TS_CONFIG,
            )
        )
        row = cr.fetchone()
        if not row:
            return None
        cr.execute(
            SQL(
                """
                SELECT token.alias,
                       array_agg(map.mapdict::bigint ORDER BY map.mapseqno)
                  FROM pg_ts_config cfg
                  JOIN pg_ts_config_map map ON map.mapcfg = cfg.oid
                  CROSS JOIN LATERAL ts_token_type(cfg.cfgparser) token
                 WHERE cfg.oid = %s
                   AND token.tokid = map.maptokentype
              GROUP BY token.alias
                """,
                row[0],
            )
        )
        return dict(cr.fetchall())

    @api.model
    def _bemade_unaccent_body_search(self, enable=True):
        """Put (``enable``) or remove the ``unaccent`` dictionary in front of
        the Knowledge dictionary for every token type of the Knowledge text
        search configuration, then rebuild the full-text index on the article
        text, which depends on that configuration.

        Idempotent: token types are read from the PostgreSQL catalog and only
        those not yet in the requested state are altered; the index is rebuilt
        only when something changed.

        :return: True when the configuration was changed
        """
        mapping = self._bemade_ts_config_mapping()
        if mapping is None:
            _logger.info(
                "Text search configuration %s not found: accent-insensitive "
                "Knowledge search not configured.",
                TS_CONFIG,
            )
            return False
        unaccent = self._bemade_ts_dictionary(UNACCENT_DICTIONARY)
        if not unaccent:
            if enable:
                # Not a warning: the addon CI fails on any warning in the log
                # and its databases are created without the extension.
                _logger.info(
                    "The PostgreSQL extension 'unaccent' is not installed in "
                    "this database: the Knowledge search keeps matching "
                    "accents in article text.",
                )
            return False
        dictionary = self._bemade_ts_dictionary(TS_DICTIONARY)
        if not dictionary:
            return False

        plain = [dictionary[0]]
        unaccented = [unaccent[0], dictionary[0]]
        source = plain if enable else unaccented
        token_types = sorted(
            alias for alias, dictionaries in mapping.items() if dictionaries == source
        )
        if not token_types:
            return False

        dictionary_sql = SQL.identifier(dictionary[1], TS_DICTIONARY)
        if enable:
            unaccent_sql = SQL.identifier(unaccent[1], UNACCENT_DICTIONARY)
            target_sql = SQL("%s, %s", unaccent_sql, dictionary_sql)
        else:
            target_sql = dictionary_sql
        self.env.cr.execute(
            SQL(
                "ALTER TEXT SEARCH CONFIGURATION %s ALTER MAPPING FOR %s WITH %s",
                SQL.identifier(TS_CONFIG),
                SQL(", ").join(SQL.identifier(alias) for alias in token_types),
                target_sql,
            )
        )
        index_name = make_index_name(self._table, "body")
        if index_exists(self.env.cr, index_name):
            self.env.cr.execute(SQL("REINDEX INDEX %s", SQL.identifier(index_name)))
        _logger.info(
            "Knowledge text search %s accents (%d token types), index %s rebuilt.",
            "ignores" if enable else "matches",
            len(token_types),
            index_name,
        )
        return True

    # ------------------------------------------------------------
    # Article titles: add the accent-insensitive title matches
    # ------------------------------------------------------------

    @api.model
    def get_sorted_articles(self, search_query, domain=False, limit=40):
        results = super().get_sorted_articles(search_query, domain=domain, limit=limit)
        if not search_query or not limit or not self.env.registry.has_unaccent:
            return results

        fold = self.env.registry.unaccent_python
        needle = fold(search_query).lower()

        def title_matches(entry):
            return needle in fold(entry.get("name") or "").lower()

        found_ids = [entry["id"] for entry in results]
        extra_articles = self.search(
            Domain(domain or Domain.TRUE)
            & Domain("is_template", "=", False)
            & Domain("name", "=ilike", f"%{escape_psql(search_query)}%")
            & Domain("id", "not in", found_ids),
            limit=limit,
            order="id desc",
        )
        # Title matches first (the standard ones, then the accent-insensitive
        # ones it missed), then the articles that only match in their text.
        extra_entries = sorted(
            (self._bemade_search_entry(article) for article in extra_articles),
            key=lambda entry: not entry["is_user_favorite"],
        )
        title_entries = [entry for entry in results if title_matches(entry)]
        other_entries = [entry for entry in results if not title_matches(entry)]
        return (title_entries + extra_entries + other_entries)[:limit]

    def _bemade_search_entry(self, article):
        """Search box entry of ``article`` (without text preview)."""
        root = article.root_article_id.sudo()
        return {
            "id": article.id,
            "icon": article.icon or False,
            "name": article.name,
            "is_user_favorite": article.is_user_favorite,
            "root_article_id": (root.id, root.display_name),
        }
