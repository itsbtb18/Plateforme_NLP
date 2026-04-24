"""Field filler mixin wrappers."""


class FieldFillerMixin:
    def _fill_translations(self, item, missing_fields, category):
        return super()._fill_translations(item, missing_fields, category)

    def _fill_choices_fields(self, item, missing_fields, category):
        return super()._fill_choices_fields(item, missing_fields, category)

    def _fill_list_fields(self, item, missing_fields, category):
        return super()._fill_list_fields(item, missing_fields, category)

    def _collect_missing_fields(self, item, fields_map):
        return super()._collect_missing_fields(item, fields_map)

    def _has_meaningful_value(self, value, config=None):
        return super()._has_meaningful_value(value, config)

    def _infer_choice(self, field_key, text_blob, choices):
        return super()._infer_choice(field_key, text_blob, choices)

    def _infer_supported_languages(self, text):
        return super()._infer_supported_languages(text)
