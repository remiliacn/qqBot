from random import choice

from player import Player
from dungeon_adventure_util.achievements import Achievements
from dungeon_adventure_util.events import Events, Event, NEED_CHOICE, ENDING, SPECIAL_ENDING


class Adventure_main:
    def __init__(self, player: Player):
        self.tempo_message = []
        self.attributes_en_to_zh = {
            'health': '血量',
            'luck': '幸运',
            'attack': '攻击'
        }
        self.status = None
        self.player = player
        self.event = Events()
        self.achievement = Achievements()

    def _change_player_luck_event(self, change):
        self.player.current_luck += change

    def _change_player_death_total(self):
        self.player.total_death += 1

    def _change_player_health_event(self, change):
        self.player.current_health += change
        if self.player.current_health < 0 and self.player.current_life == 1:
            self.event.set_next_event(self.event.get_event_by_event_id('10000'))
            self.game_over()
        elif self.player.current_health < 0:
            self.player.current_health = self.player.base_health
            self.player.current_life -= 1

    def _change_player_attack_event(self, change):
        self.player.current_attack += change

    def change_player_step_event(self, change):
        self.player.parse_talent_activate_condition()
        self.player.current_step += change
        # check if player is alive.
        self._change_player_health_event(0)

    def _parse_changes_from_event(self, change: dict):
        if 'health' in change:
            self._change_player_health_event(change['health'])

        if 'attack' in change:
            self._change_player_attack_event(change['attack'])

        if 'luck' in change:
            self._change_player_luck_event(change['luck'])

    def next(self) -> Event:
        event = self.event.get_next_event(self.player.current_luck, self.player.current_step)
        self.change_player_step_event(1)

        if event.change is not None:
            self._parse_changes_from_event(event.change)

        if event.unlock_achievement is not None:
            for ach in event.unlock_achievement:
                self.win_achievement(ach)

        self.status = event.status
        return event

    def win_achievement(self, ach_id: str):
        result = self.achievement.win_achievement(ach_id)
        if result:
            self.tempo_message.append(f'解锁成就：{result["title"]}！\n'
                                      f'【{result["description"]}'
                                      f'（{result["unlock_instruction"]}）】')

    def _binary_choose_handler(self, event_choose: dict):
        trigger_event = event_choose['triggerEvent']
        if not isinstance(trigger_event, str):
            trigger_event = choice(trigger_event)
        event = self.event.get_event_by_event_id(trigger_event)
        return event

    def choose_a(self, event):
        event_first_literal = event.binary_choice.first_choice
        event_first_packed = self._binary_choose_handler(event_first_literal)
        self.event.set_next_event(event_first_packed)

    def choose_b(self, event):
        event_second_literal = event.binary_choice.second_choice
        event_second_packed = self._binary_choose_handler(event_second_literal)
        self.event.set_next_event(event_second_packed)

    def _parse_change_to_string(self, change: dict):
        response = ', '.join(
            [
                self.attributes_en_to_zh[key]
                + f'{"+" + str(value) if value > 0 else {value} }' for key, value in change.items()
            ]
        )

        return response

    def event_to_literal(self, event: Event):
        achievement_message = "\n".join(self.tempo_message) + '\n'
        self.tempo_message.clear()
        message = f'{achievement_message}' \
                  f'{event.description}' \
                  f'{" 【" + self._parse_change_to_string(event.change) + "】" if event.change is not None else ""}'

        for talent in self.player.player_talent:
            if talent.talent_id == "65":
                message += '喵~'

            if talent.talent_id == "59":
                message = message[::-1]

            if talent.talent_id == "85":
                message += '哼哼哼啊啊啊啊~'

        return message

    def binary_choose(self, query: str, event: Event):
        query = query.lower().strip()
        if query not in ('y', '1', 'yes', 'a', 'b', '2', 'n', 'no'):
            self.win_achievement('1053')

        if query in ('y', '1', 'yes', 'a'):
            self.choose_a(event)
        else:
            self.choose_b(event)

    def change_player_by_event(self, event: Event):
        if event.change is not None:
            changes = event.change
            for key, change in changes.items():
                if key == 'luck':
                    self._change_player_luck_event(change)
                elif key == 'health':
                    self._change_player_health_event(change)
                elif key == 'attack':
                    self._change_player_attack_event(change)

        if not self._check_if_player_is_alive():
            self.game_over()

    def _check_if_player_is_alive(self):
        return self.player.current_life > 0

    def game_over(self):
        self._change_player_death_total()
        self.event.set_next_event(self.event.get_event_by_event_id('10000'))


def init_game():
    # init player
    test_player = Player('634915227')
    game = Adventure_main(test_player)
    return game


def talent_choose_phase(game):
    # talent choose phase
    random_talent = game.player.get_random_talents()
    allowed_talent_list = [x.talent_id for x in random_talent]
    print(game.player.talents.get_talent_message_by_list(random_talent))

    choose_talent = input('choose talent: ')

    success = False
    message = ''
    while not success:
        success, message, talent_list = game.player.choose_talent(choose_talent, allowed_talent_list)
        if success and talent_list is not None:
            for t in talent_list:
                if t.unlock_achievement is not None:
                    for ach in t.unlock_achievement:
                        game.win_achievement(ach)
            break

        if not success:
            input(message)

    return message


def game_start(game):
    # get start event
    a = game.event.get_start_event(True)
    game.change_player_step_event(1)
    print(game.event_to_literal(a))
    game.change_player_by_event(a)


def game_next_event(game):
    next_event = game.next()
    print(game.event_to_literal(next_event))
    game.change_player_by_event(next_event)

    if game.status == NEED_CHOICE:
        # TODO: show binary choose prompt
        print(next_event.binary_choice.get_option_literal())
        choose = input('your choice?')
        game.binary_choose(choose, next_event)

    input('next?')


def main():
    game = init_game()

    message = talent_choose_phase(game)
    if message == 'Death_lol':
        game.win_achievement('1025')
        game.game_over()

    game_start(game)

    # get next event
    while game.status != ENDING and game.status != SPECIAL_ENDING:
        game_next_event(game)


if __name__ == '__main__':
    main()
