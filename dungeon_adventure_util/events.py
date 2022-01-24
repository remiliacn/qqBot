from json import loads
from os import getcwd
from random import choice, randint

from dungeon_adventure_util.utils import get_data

START = 'start'
BUFF = 'buff'
DEBUFF = 'debuff'
NEUTRAL = "neutral"
RESERVED = "reserved"
NEED_CHOICE = "need_choice"
BLAH = "blah"
ENDING = "ending"
SPECIAL_ENDING = "special_ending"
SCRPIPTED = "scripted"
CHOOSE_COMPLETED = "choose_completed"

STATUS_TUPLE = (BLAH, NEUTRAL, NEED_CHOICE)
ENDING_TUPLE = (ENDING, SPECIAL_ENDING)

CAN_RANDOM = 'can_random'
STATUS = 'status'


class Event:
    def __init__(self, event_dict: dict):
        self.description = event_dict['description']
        self.can_random = event_dict[CAN_RANDOM]
        self.status = event_dict[STATUS]
        self.one_time_use = event_dict['one_time_use']
        self.change = get_data(event_dict, 'change')
        self.change_death = get_data(event_dict, 'change_death')
        self.sets = get_data(event_dict, 'set')
        self.add_event = get_data(event_dict, 'add_event')
        self.unlock_achievement = get_data(event_dict, 'unlock_achievement')
        self.add_item = get_data(event_dict, 'add_item')
        self.exclude_event = get_data(event_dict, 'exclude_event')
        self.binary_choice = BinaryChoice(get_data(event_dict, 'binary_choice'))
        self.force_next = get_data(event_dict, 'force_next')


class Events:
    def __init__(self):
        self.event_dict = self._read_event_file()
        self.event_dict: dict = self.event_dict['events']
        self.next_event = None

        self.dedupe_event_set = set()
        self.sort_event_dict = {}

        self._sort_out_the_event_dict()

    def get_next_event(self, user_luck, steps) -> Event:
        event = self.get_random_event_by_status(user_luck, steps)
        return event

    def set_next_event(self, next_event: Event) -> bool:
        if next_event is None:
            return False

        self.next_event = next_event

    def _sort_out_the_event_dict(self):
        for event_id, event in self.event_dict.items():
            status = event['status']
            can_random = event[CAN_RANDOM]
            if status not in self.sort_event_dict:
                self.sort_event_dict[status] = []

            if can_random or status == START:
                self.sort_event_dict[status].append(event_id)

    @staticmethod
    def _get_special_ending_chance(steps, is_eval_on, enabled):
        if not enabled:
            return 0

        if steps < 10:
            return 0

        if is_eval_on and steps >= 40:
            return 10000

        if enabled and steps >= 40:
            return 5

    def _get_random_status(self, user_luck, steps, is_eval_on=False, enabled=False) -> str:
        random_chance = randint(0, 10000)
        special_ending_odd = self._get_special_ending_chance(steps, is_eval_on, enabled)
        if random_chance < 1000 and 20 <= steps <= 30:
            return ENDING
        if random_chance < 8000 and steps > 30:
            return ENDING

        if random_chance < special_ending_odd:
            return SPECIAL_ENDING

        if random_chance < 2500 + special_ending_odd + user_luck * 100:
            return BUFF

        if random_chance < 5000 + special_ending_odd - user_luck * 100:
            return DEBUFF

        if random_chance < 6500 + special_ending_odd:
            return NEED_CHOICE

        if random_chance < 7500 + special_ending_odd:
            return BLAH

        return NEUTRAL

    def _check_dedupes(self, status: str):
        dedupe_list = []
        for event in self.sort_event_dict[status]:
            if event not in self.dedupe_event_set:
                dedupe_list.append(event)

        return dedupe_list

    def _remove_event_id_from_sorted_list(self, event_id):
        for key, value in self.sort_event_dict.items():
            if event_id in value:
                self.sort_event_dict[key].remove(event_id)

    def get_random_event_by_status(self, user_luck, steps, is_eval_on=False, enabled=False, status=None) -> Event:
        if self.next_event is not None:
            next_event = self.next_event
            self.next_event = None
            return next_event

        if status is None:
            status = self._get_random_status(user_luck, steps, is_eval_on, enabled)

        if status not in self.sort_event_dict:
            raise ValueError('wtf?')

        if not self.sort_event_dict[status]:
            for s in STATUS_TUPLE:
                deduped_list = self._check_dedupes(s)
                if deduped_list:
                    break
            else:
                return self.get_event_by_event_id("E10002")
        else:
            deduped_list = self.sort_event_dict[status]

        event_id = choice(deduped_list)
        while event_id in self.dedupe_event_set:
            event_id = choice(self.sort_event_dict[status])

        event = self.get_event_by_event_id(event_id)
        if event.exclude_event is not None:
            for e in event.exclude_event:
                self.dedupe_event_set.add(e)
                self._remove_event_id_from_sorted_list(e)

        if event.one_time_use:
            self.dedupe_event_set.add(event_id)
            self.sort_event_dict[event.status].remove(event_id)

        if event.add_event is not None:
            to_add_event = event.add_event
            for event_to_add in to_add_event:
                event_add = self.get_event_by_event_id(event_to_add)
                self.sort_event_dict[event_add.status].append(event_to_add)

        if event.force_next is not None:
            self.next_event = event.force_next
        return event

    def get_start_event(self, first_start=False):
        if not first_start:
            random_chance = randint(0, 1000)
            if random_chance < 2:
                start_event = self.get_event_by_event_id("10007")
            else:
                start_event = self.get_random_event_by_status(0, 0, status=START)
        else:
            start_event = self.get_event_by_event_id("10001")

        if start_event.force_next is not None:
            self.next_event = start_event.force_next

        return start_event

    def get_event_by_event_id(self, event_id: str) -> Event:
        if event_id not in self.event_dict:
            raise ValueError('Invalid event id.')

        event = self.event_dict[event_id]
        event = Event(event)

        return event

    @staticmethod
    def _read_event_file():
        with open(f'{getcwd()}/data/adventure_data/event.json', encoding='utf-8-sig') as file:
            json_data = loads(file.read())

        return json_data


class BinaryChoice(Events):
    def __init__(self, binary_choice_dict):
        super().__init__()
        self.first_choice = None
        self.second_choice = None

        self.trigger_event = None
        self.trigger_prompt = None

        if binary_choice_dict is not None:
            self.first_choice = binary_choice_dict["A"]
            self.second_choice = binary_choice_dict["B"]

    def get_option_literal(self):
        return f'A: {self.first_choice["prompt"]}\n' \
               f'B: {self.second_choice["prompt"]}'

    def choose_your_destiny(self, query: str) -> dict:
        query = query.lower()
        if query in ('1', 'a', 'y', 'yes'):
            return self.first_choice

        return self.second_choice
