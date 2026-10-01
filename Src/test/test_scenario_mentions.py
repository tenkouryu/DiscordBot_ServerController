import unittest

from function.scenario.scenario_service import resolve_scenario_mentions


class ScenarioMentionTests(unittest.TestCase):
    def test_text_without_mentions_skips_guild_member_lookup(self):
        class GuildStub:
            @property
            def roles(self):
                raise AssertionError("roles should not be read")

            @property
            def members(self):
                raise AssertionError("members should not be read")

        text = "シナリオを開始します"
        self.assertEqual(resolve_scenario_mentions(text, GuildStub()), text)


if __name__ == "__main__":
    unittest.main()