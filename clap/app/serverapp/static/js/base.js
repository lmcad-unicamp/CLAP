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
    now = moment().toString();

    if (msg_type == 'success'){
        $("#"+div_id).replaceWith(`
            <div class="alert alert-dismissible alert-success">
                <button type="button" class="close" data-dismiss="alert">&times;</button>
                <div class="row justify-content-end">
                    <div class="col-9">
                        <p> ${msg} </p>
                    </div>
                    <div class="col-3">
                        <div class="float-right">
                            <small>${now}</small>
                        </div>
                    </div>
                </div> 
            </div>`
        )
    }

    else if(msg_type == 'fail'){
        $("#"+div_id).replaceWith(`
            <div class="alert alert-dismissible alert-danger">
                <button type="button" class="close" data-dismiss="alert">&times;</button>
                <div class="row justify-content-end">
                    <div class="col-9">
                        <p> ${msg} </p>
                    </div>
                    <div class="col-3">
                        <div class="float-right">
                            <small>${now}</small>
                        </div>
                    </div>
                </div> 
            </div>`
        )
    }


}