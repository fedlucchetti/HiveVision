
#UserInfo will be interacted with through this class. Basis for basic auth.
class User(object):

    def __init__(self, mon_client=None):
        self.mon_client = mon_client
        db_mon = mon_client['hivizens']
        coll_bees = db_mon['bees']
        #returns a list type
        self.usernames = coll_bees.distinct('username')