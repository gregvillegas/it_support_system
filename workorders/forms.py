from django import forms
from django.contrib.auth.models import User
from .models import WorkOrder, WorkOrderComment, TaskType, TaskCategory


class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = [
            'title', 'description', 'task_type', 'task_category', 
            'priority', 'assigned_to', 'location_name', 'latitude', 
            'longitude', 'due_date', 'difficulty_rating'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set current user as requester if creating new work order
        if user:
            self.instance.requester = user
        
        # Filter assigned_to to only include staff users
        self.fields['assigned_to'].queryset = User.objects.filter(is_staff=True)
        
        # Add Bootstrap classes
        for field_name, field in self.fields.items():
            if field_name not in ['latitude', 'longitude']:
                field.widget.attrs['class'] = 'form-control'


class WorkOrderCommentForm(forms.ModelForm):
    class Meta:
        model = WorkOrderComment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class WorkOrderStatusForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class LocationForm(forms.Form):
    location_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter location name'})
    )
    latitude = forms.FloatField(widget=forms.HiddenInput())
    longitude = forms.FloatField(widget=forms.HiddenInput())
