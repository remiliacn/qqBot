import pickle
import time
from os import getcwd
from os.path import exists
from random import choice

from dungeon_adventure_util.achievements import Achievements
from dungeon_adventure_util.events import Events, Event, NEED_CHOICE, CHOOSE_COMPLETED, \
    ENDING_TUPLE, START
from player import Player


class AdventureMain:
    def __init__(self, player: Player):
        self.tempo_message = []
        self.attributes_en_to_zh = {
            'health': '血量',
            'luck': '幸运',
            'attack': '攻击'
        }
        self.status = None
        self.player = player
        self.player.last_updated_time = time.time()
        self.event = Events()
        self.achievement = Achievements()

    def refresh_event(self):
        self.event = Events()

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
        if self.status == NEED_CHOICE:
            return self.player.current_event

        event = self.event.get_next_event(self.player.current_luck, self.player.current_step)
        self.change_player_step_event(1)

        if event.change is not None:
            self._parse_changes_from_event(event.change)

        if event.unlock_achievement is not None:
            for ach in event.unlock_achievement:
                self.win_achievement(ach)

        self.status = event.status
        self.player.current_event = event
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

        self.status = CHOOSE_COMPLETED

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

    def game_finished(self):
        self.player.total_played += 1
        self.player.talent_set.clear()
        self.player.player_talent.clear()


class UserAdventure:
    def __init__(self):
        self.group_stat = {}
        self.game_file_place = f'{getcwd()}/data/adventure_data/gamefile.dat'
        self.group_stat = self._read_from_file()

    def _read_from_file(self):
        if exists(self.game_file_place):
            with open(self.game_file_place, 'rb') as file:
                self.group_stat = pickle.load(file)

        return self.group_stat

    def save_game_by_user(self, user_id, adventure: AdventureMain):
        user_id = str(user_id)
        if user_id not in self.group_stat:
            self.group_stat[user_id] = {}

        self.group_stat[user_id] = adventure
        with open(self.game_file_place, 'wb') as file:
            pickle.dump(self.group_stat, file, protocol=2)

    def load_game_by_user(self, user_id) -> AdventureMain:
        try:
            game = self.group_stat[user_id]
        except KeyError:
            player = Player(str(user_id))
            game = AdventureMain(player)

        return game


game_main = UserAdventure()


def talent_choose_phase(user_id):
    # talent choose phase
    game = game_main.load_game_by_user(user_id)

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

    game_main.save_game_by_user(user_id, game)
    return message


def game_start(user_id) -> AdventureMain:
    # get start event
    game = game_main.load_game_by_user(user_id)
    start_event = game.event.get_start_event(True)
    game.change_player_step_event(1)
    game.status = START
    print(game.event_to_literal(start_event))
    game.change_player_by_event(start_event)
    return game


def game_next_event(user_id) -> AdventureMain:
    game = game_main.load_game_by_user(user_id)

    next_event = game.next()
    print(game.event_to_literal(next_event))
    game.change_player_by_event(next_event)

    game_main.save_game_by_user(user_id, game)

    if game.status == NEED_CHOICE:
        print(next_event.binary_choice.get_option_literal())
        choose = input('your choice?')
        game.binary_choose(choose, next_event)

    input('next?')
    return game


def main(user_id):
    game = game_main.load_game_by_user(user_id)

    if not game.player.talent_set or game.status in ENDING_TUPLE:
        game.refresh_event()
        game.player.reset_player()
        message = talent_choose_phase(user_id)
        if message == 'Death_lol':
            game.win_achievement('1025')
            game.game_over()

        game = game_start(user_id)

    # get next event
    while game.status not in ENDING_TUPLE:
        game = game_next_event(user_id)

    game.game_finished()


if __name__ == '__main__':
    main('634915227')
