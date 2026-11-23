class OrganizationNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class MemberNotFoundError(Exception):
    pass


class DuplicateOrganizationMemberError(Exception):
    pass


class OrganizationOwnerError(Exception):
    pass


class SelfRemovalError(Exception):
    pass


class ProjectNotFoundError(Exception):
    pass
