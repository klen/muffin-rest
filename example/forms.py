import muffin_rest as mr


class ResourceForm(mr.Form):

    active = mr.BooleanField()
    name = mr.CharField()
