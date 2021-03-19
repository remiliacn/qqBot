import json
import uuid


class WeebController:
    def __init__(self):
        self.weeb_file_path = 'data/learning/weebThings.json'
        self.weeb_holder_path = 'data/learning/weebApprovalHolder.json'
        self.weeb_dict = {}
        self.weeb_dict_waiting_list = {}
        self.weeb_dict = self._get_weeb_dict_from_file()
        self.INFO_NOT_AVAILABLE = '啊~还没有二刺猿发言的说喵~~~要不要试试' \
                                  '"！我教你怪话"命令来教教我么么哒~~'

    def _get_weeb_dict_from_file(self) -> dict:
        try:
            with open(self.weeb_file_path, 'r+', encoding='utf-8') as file:
                json_data = json.loads(file.read())
                return json_data
        except Exception as err:
            print(err)
            return {}

    def _get_waiting_list_from_file(self) -> dict:
        try:
            with open(self.weeb_holder_path, 'r+', encoding='utf-8') as file:
                json_data = json.loads(file.read())
                return json_data
        except Exception as err:
            print(err)
            return {}

    def get_weeb_reply_by_keyword(self, keyword: str):
        return self.weeb_dict[keyword] \
            if keyword in self.weeb_dict \
            else self.INFO_NOT_AVAILABLE

    def set_weeb_word_wait_approve(self, keyword: str, response: str) -> (str, str, str):
        if keyword in self.weeb_dict:
            if response in self.weeb_dict[keyword]:
                return '', '', ''

        uuid_for_response = str(uuid.uuid4())
        self.weeb_dict_waiting_list[uuid_for_response] = {
            'keyword': keyword,
            'response': response
        }

        self.make_a_json(self.weeb_holder_path, self.weeb_dict_waiting_list)
        return uuid_for_response, keyword, response

    def set_weeb_word_to_main_dict(self, uid: str, decision: bool) -> bool:
        self.weeb_dict_waiting_list = self._get_waiting_list_from_file()
        if decision:
            if uid in self.weeb_dict_waiting_list:
                parent_node = self.weeb_dict_waiting_list[uid]
                keyword = parent_node['keyword']
                response = parent_node['response']
                if keyword not in self.weeb_dict:
                    self.weeb_dict[keyword] = []

                self.weeb_dict[keyword].append(response)
                del self.weeb_dict_waiting_list[uid]
                self.make_a_json(self.weeb_file_path, self.weeb_dict)
                self.make_a_json(self.weeb_holder_path, self.weeb_dict_waiting_list)

                return True

        if uid in self.weeb_dict_waiting_list:
            del self.weeb_dict_waiting_list[uid]
            self.make_a_json(self.weeb_holder_path, self.weeb_dict_waiting_list)
            return True

        return False

    def make_a_json(self, file_name: str, content: dict):
        if file_name == self.weeb_file_path or self.weeb_holder_path:
            with open(file_name, 'w+') as file:
                json.dump(content, file, indent=4)
