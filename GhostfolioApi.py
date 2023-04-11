import json

import requests

import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class GhostfolioApi:

    def __init__(self, ghost_host, ghost_token, ghost_currency):
        self.ghost_token = ghost_token
        self.ghost_host = ghost_host
        self.ghost_currency = ghost_currency
        # todo: desired name to show in ghostfolio
        self.ghost_account_sync_name = "IBKR"
        # todo: Id as in ghostfolio
        self.platform_id = None

    def update_account(self, account_id, account):
        url = f"{self.ghost_host}/api/v1/account/{account_id}"

        payload = json.dumps(account)
        headers = {
            'Authorization': f"Bearer {self.ghost_token}",
            'Content-Type': 'application/json'
        }
        try:
            logger.debug(f"update_account {url}: {account}")
            response = requests.request("PUT", url, headers=headers, data=payload)
        except Exception as e:
            logger.error(e)
            return False
        if response.status_code == 200:
            logger.info(f"Updated Cash for account {response.json()['id']}")
        else:
            logger.warning(f"Failed create: {response.text}")
        return response.status_code == 200

    def delete_activity(self, act_id):
        url = f"{self.ghost_host}/api/v1/order/{act_id}"

        payload = {}
        headers = self.__get_header_with_ghostfolio_auth()
        try:
            logger.debug(f"delete_activity {url}")
            response = requests.request("DELETE", url, headers=headers, data=payload)
        except Exception as e:
            logger.error(e)
            return False

        return response.status_code == 200

    def lookup_asset(self, query):
        url = f"{self.ghost_host}/api/v1/symbol/lookup?query={query}"
        headers = self.__get_header_with_ghostfolio_auth()
        try:
            response = requests.request("GET", url, headers=headers)
            return self.validate_and_convert_response_to_assets(response)
        except Exception as e:
            logger.error("lookup asset failed:")
            logger.error(e)
            return False, None

    @staticmethod
    def validate_and_convert_response_to_assets(response):
        if response.status_code == 200:
            items = response.json().get('items')
            if len(items) > 1:
                # inform fuzzy match, but still do it :D
                logger.info("fuzzy match to first symbol for %s in %s",
                            response.request.url,
                            items)
            if len(items) >= 1:
                return True, items[0]
            return False, None
        else:
            raise Exception(response)

    def get_all_activities(self):
        url = f"{self.ghost_host}/api/v1/order"

        payload = {}
        headers = self.__get_header_with_ghostfolio_auth()
        try:
            logger.debug(f"get_all_activities {url}")
            response = requests.request("GET", url, headers=headers, data=payload)
        except Exception as e:
            logger.warning("error while fetching all activities: %s", e)
            return []

        if response.status_code == 200:
            return response.json()['activities']
        else:
            return []

    def import_activities(self, bulk):
        chunks = self.__generate_chunks(bulk, 10)
        for acts in chunks:
            url = f"{self.ghost_host}/api/v1/import"
            formatted_acts = json.dumps(
                {"activities": sorted(acts, key=lambda x: x["date"])}
            )
            payload = formatted_acts
            headers = {
                'Authorization': f"Bearer {self.ghost_token}",
                'Content-Type': 'application/json'
            }
            logger.info("Adding activities: \n" + formatted_acts)
            try:
                response = requests.request("POST", url, headers=headers, data=payload)
            except Exception as e:
                logger.warning(e)
                return False
            if response.status_code == 201:
                logger.info(f"created {formatted_acts}")
            else:
                logger.warning("Failed create: " + response.text)
            if response.status_code != 201:
                return False
        return True

    def add_activity(self, act):
        url = f"{self.ghost_host}/api/v1/order"

        payload = json.dumps(act)
        headers = {
            'Authorization': f"Bearer {self.ghost_token}",
            'Content-Type': 'application/json'
        }
        logger.info("Adding activity: " + json.dumps(act))
        try:
            response = requests.request("POST", url, headers=headers, data=payload)
        except Exception as e:
            logger.error(e)
            return False
        if response.status_code == 201:
            logger.info(f"created {response.json()['id']}")
        else:
            logger.error("Failed create: " + response.text)
        return response.status_code == 201

    def create_or_get_ibkr_account_id(self):
        accounts = self.get_ghostfolio_accounts()
        for account in accounts:
            if account["name"] == self.ghost_account_sync_name:
                return account["id"]
        return self.__create_ibkr_account()

    def __create_ibkr_account(self):
        account = {
            "accountType": "SECURITIES",
            "balance": 0,
            "currency": self.ghost_currency,
            "isExcluded": False,
            "name": self.ghost_account_sync_name,
            "platformId": self.platform_id,
        }
        return self.create_account(account)

    def delete_all_activities(self):
        account_id = self.create_or_get_ibkr_account_id()
        acts = self.get_all_activities_for_account(account_id)

        if not acts:
            logger.info("No activities to delete")
            return True
        complete = True

        for act in acts:
            if act['accountId'] == account_id:
                act_complete = self.delete_activity(act['id'])
                complete = complete and act_complete
                if act_complete:
                    logger.info("Deleted: %s", act['id'])
                else:
                    logger.warning("Failed Delete: %s", act['id'])
        return complete

    def get_all_activities_for_account(self, account_id):
        acts = self.get_all_activities()
        filtered_acts = []
        for act in acts:
            if act['accountId'] == account_id:
                filtered_acts.append(act)
        return filtered_acts

    def create_account(self, account):
        url = f"{self.ghost_host}/api/v1/account"

        payload = json.dumps(account)
        headers = {
            'Authorization': f"Bearer {self.ghost_token}",
            'Content-Type': 'application/json'
        }
        try:
            response = requests.request("POST", url, headers=headers, data=payload)
        except Exception as e:
            print(e)
            return ""
        if response.status_code == 201:
            return response.json()["id"]
        logger.warning(f"create_account: Failed creating {url}: {account}")
        return ""

    def get_ghostfolio_accounts(self):
        url = f"{self.ghost_host}/api/v1/account"

        payload = {}
        headers = self.__get_header_with_ghostfolio_auth()
        try:
            response = requests.request("GET", url, headers=headers, data=payload)
        except Exception as e:
            logger.error(e)
            return []
        if response.status_code == 200:
            return response.json()['accounts']
        else:
            raise Exception(response)

    def get_ticker(self, isin, symbol):
        # for now only yahoo
        data_source = "YAHOO"
        successful, ticker = self.lookup_asset(isin)
        if not successful:
            successful, ticker = self.lookup_asset(symbol)
            if not successful:
                raise Exception(f"no symbol found for {isin} {symbol}")
        return data_source, ticker.get('symbol'), ticker.get('currency')

    @staticmethod
    def __generate_chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def __get_header_with_ghostfolio_auth(self):
        return {
            'Authorization': f"Bearer {self.ghost_token}",
        }