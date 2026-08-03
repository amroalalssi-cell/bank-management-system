class User:

    def __init__(self, username, password, role, customer_id=None):

        self.username = username

        self.password = password

        self.role = role

        self.customer_id = customer_id