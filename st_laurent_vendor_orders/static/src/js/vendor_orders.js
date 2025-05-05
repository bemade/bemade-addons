/* JavaScript pour le module de commandes vendeur */
$(document).ready(function() {
    // Fonction pour mettre à jour le statut d'une commande
    function updateOrderStatus(orderId, status) {
        $.ajax({
            url: '/my/vendor/orders/update_status',
            type: 'POST',
            data: {
                'order_id': orderId,
                'status': status,
                'csrf_token': odoo.csrf_token,
            },
            success: function(result) {
                if (result.success) {
                    window.location.reload();
                } else {
                    alert(result.error || "Une erreur s'est produite lors de la mise à jour du statut.");
                }
            },
            error: function() {
                alert("Une erreur s'est produite lors de la communication avec le serveur.");
            }
        });
    }

    // Gestionnaire d'événements pour le bouton de traitement de commande
    $('.btn-process-order').on('click', function(e) {
        e.preventDefault();
        var orderId = $(this).data('order-id');
        updateOrderStatus(orderId, 'processing');
    });

    // Validation du formulaire d'expédition
    $('#vendor-order-ship-form').on('submit', function(e) {
        var trackingNumber = $('#tracking_number').val();
        var carrierId = $('#carrier_id').val();
        
        if (!trackingNumber || !carrierId) {
            e.preventDefault();
            alert("Veuillez fournir un numéro de suivi et sélectionner un transporteur.");
            return false;
        }
        
        return true;
    });

    // Filtrage des commandes par statut
    $('.vendor-order-filter').on('click', function(e) {
        e.preventDefault();
        var filterValue = $(this).data('filter');
        
        // Mettre à jour l'URL avec le paramètre de filtre
        var url = new URL(window.location.href);
        url.searchParams.set('filterby', filterValue);
        window.location.href = url.toString();
    });

    // Tri des commandes
    $('.vendor-order-sort').on('click', function(e) {
        e.preventDefault();
        var sortValue = $(this).data('sort');
        
        // Mettre à jour l'URL avec le paramètre de tri
        var url = new URL(window.location.href);
        url.searchParams.set('sortby', sortValue);
        window.location.href = url.toString();
    });

    // Copier le numéro de suivi dans le presse-papiers
    $('.copy-tracking').on('click', function(e) {
        e.preventDefault();
        var trackingNumber = $(this).data('tracking');
        
        // Créer un élément temporaire pour copier le texte
        var $temp = $("<input>");
        $("body").append($temp);
        $temp.val(trackingNumber).select();
        document.execCommand("copy");
        $temp.remove();
        
        // Afficher un message de confirmation
        var $tooltip = $(this).find('.tooltip-text');
        $tooltip.text('Copié!');
        setTimeout(function() {
            $tooltip.text('Copier');
        }, 2000);
    });
});
