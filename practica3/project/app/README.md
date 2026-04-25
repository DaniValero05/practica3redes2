# Django app templates 

Assumes there're following views as urls:

  - `app:devices

     List all devices

  - `app:device_detail`

     Shows the detail of a Device

  - `app:device_new`

     Shows the form to add a Device. Called when saving. 

  - `app:device_edit`

     Shows the form to modify a Device. Called when saving. 

  - `app:device_remove`

     Removes a Device


Views might be changed but original views expect them.
Recomendations:
  - Use generic.ListView or generic.DetailView
  - Follow the tutorial for examples for add and modify
