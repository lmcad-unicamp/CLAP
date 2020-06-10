function save_content() {
    div_id = "notification-"+moment().unix().toString()
    div_notification = document.createElement('div');
    div_notification.setAttribute("id", div_id);
    $("#notificationHolder").prepend(div_notification)

    $.post('save-configuration', {"config_type": "{{ config_type }}", "content": editor.getValue()}, 
        function(response){
            now = moment().toString();
            $("#"+div_id).replaceWith(`
            <div class="alert alert-dismissible alert-success">
                <button type="button" class="close" data-dismiss="alert">&times;</button>
                ${now} -- <strong>Content successfully saved</strong> (${response})
            </div>`
        )
    }).fail( function(response) {
        now = moment().toString();
        $("#"+div_id).replaceWith(`
            <div class="alert alert-dismissible alert-danger">
                <button type="button" class="close" data-dismiss="alert">&times;</button>
                ${now} -- <strong>Fail to save content:</strong> ${response.responseText}
            </div>`
    )})
}

function add_notification(msg_type, msg){
    div_id = "notification-"+moment().unix().toString()
    div_notification = document.createElement('div');
    div_notification.setAttribute("id", div_id);
    $("#notificationHolder").prepend(div_notification)
    moment().locale()
    now = moment().format('lll').toString();
    text_to_replace = ""

    if (msg_type == 'success')
        text_to_replace = ` <div class="alert alert-dismissible alert-success">`
    else if(msg_type == 'fail')
        text_to_replace = ` <div class="alert alert-dismissible alert-danger">`
    else 
        return ""

    text_to_replace += `
        <button type="button" class="close" data-dismiss="alert">&times;</button>
            <div class="row justify-content-end">
                <div class="col">
                    <small> ${msg} </small>
                </div>
                <div class="col-12 col-sm-auto">
                    <small>${now}</small>
                </div>
            </div> 
        </div>`

    $("#"+div_id).replaceWith(text_to_replace)
}