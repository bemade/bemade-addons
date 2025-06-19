odoo.define('portal_planning.calendar', (require) => {

    const publicWidget = require('web.public.widget');
    const core = require('web.core');
    const time = require('web.time');
    const ajax = require('web.ajax');
    const _t = core._t;

    publicWidget.registry.PlanningCalendar = publicWidget.Widget.extend({
        selector: '.o_portal_planning_calendar',
        events: {
            'click .o_planning_slot_confirm': '_onConfirmSlot',
            'click .o_planning_slot_modify': '_onModifySlot',
            'click .o_planning_slot_exchange': '_onExchangeSlot'
        },

        /**
         * @override
         */
        start() {
            return this._super.apply(this, arguments).then(() => {
                this._initCalendar();
            });
        },

        /**
         * Initialise le calendrier FullCalendar
         *
         * @private
         */
        _initCalendar() {
            const calendarEl = this.$el.find('.o_calendar_container')[0];
            
            if (!calendarEl) {
                console.error('Élément calendrier non trouvé');
                return;
            }

            const calendar = new FullCalendar.Calendar(calendarEl, {
                initialView: 'timeGridWeek',
                headerToolbar: {
                    left: 'prev,next today',
                    center: 'title',
                    right: 'dayGridMonth,timeGridWeek,timeGridDay'
                },
                locale: 'fr',
                firstDay: 1, // Lundi
                allDaySlot: false,
                slotMinTime: '06:00:00',
                slotMaxTime: '22:00:00',
                slotDuration: '00:30:00',
                eventTimeFormat: {
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                },
                nowIndicator: true,
                navLinks: true,
                selectable: false,
                selectMirror: true,
                eventClick: (info) => {
                    this._onEventClick(info);
                },
                events: (info, successCallback, failureCallback) => {
                    this._loadEvents(info.start, info.end, successCallback, failureCallback);
                },
                eventDidMount: (info) => {
                    $(info.el).popover({
                        title: info.event.title,
                        content: self._formatEventPopover(info.event),
                        trigger: 'hover',
                        placement: 'top',
                        container: 'body',
                        html: true
                    });
                }
            });

            calendar.render();
            this.calendar = calendar;
        },

        /**
         * Charge les événements du calendrier
         *
         * @private
         * @param {Date} start - Date de début
         * @param {Date} end - Date de fin
         * @param {Function} successCallback - Fonction de rappel en cas de succès
         * @param {Function} failureCallback - Fonction de rappel en cas d'échec
         */
        _loadEvents(start, end, successCallback, failureCallback) {
            ajax.jsonRpc('/planning/api/slots', 'call', {
                start_date: moment(start).format('YYYY-MM-DD'),
                end_date: moment(end).format('YYYY-MM-DD')
            }).then((data) => {
                const events = [];
                if (data.success) {
                    _.each(data.slots, (slot) => {
                        let color;
                        switch (slot.portal_status) {
                            case 'draft':
                                color = '#17a2b8'; // info
                                break;
                            case 'confirmed':
                                color = '#28a745'; // success
                                break;
                            case 'modified':
                                color = '#ffc107'; // warning
                                break;
                            case 'pending_approval':
                                color = '#dc3545'; // danger
                                break;
                            default:
                                color = '#6c757d'; // secondary
                        }

                        events.push({
                            id: slot.id,
                            title: slot.name || (slot.role_id ? slot.role_id[1] : _t('Créneau de planning')),
                            start: slot.start_datetime,
                            end: slot.end_datetime,
                            allDay: false,
                            backgroundColor: color,
                            borderColor: color,
                            extendedProps: {
                                slot: slot
                            }
                        });
                    });
                    successCallback(events);
                } else {
                    failureCallback(data.error || _t("Erreur lors du chargement des créneaux"));
                }
            }).guardedCatch(function (error) {
                failureCallback(error);
            });
        },

        /**
         * Formate le contenu de la popover pour un événement
         *
         * @private
         * @param {Object} event - Événement FullCalendar
         * @returns {String} - Contenu HTML de la popover
         */
        _formatEventPopover(event) {
            const slot = event.extendedProps.slot;
            const start = moment(slot.start_datetime);
            const end = moment(slot.end_datetime);
            const duration = moment.duration(end.diff(start));
            const hours = Math.floor(duration.asHours());
            const minutes = Math.floor(duration.asMinutes()) % 60;
            
            let html = '<div class="o_planning_popover">';
            
            if (slot.role_id) {
                html += '<p><strong>' + _t('Rôle') + ':</strong> ' + slot.role_id[1] + '</p>';
            }
            
            html += '<p><strong>' + _t('Date') + ':</strong> ' + start.format('DD/MM/YYYY') + '</p>';
            html += '<p><strong>' + _t('Horaire') + ':</strong> ' + start.format('HH:mm') + ' - ' + end.format('HH:mm') + '</p>';
            html += '<p><strong>' + _t('Durée') + ':</strong> ' + hours + 'h' + (minutes ? ' ' + minutes + 'min' : '') + '</p>';
            
            if (slot.portal_status) {
                var status;
                switch (slot.portal_status) {
                    case 'draft':
                        status = '<span class="badge badge-info">' + _t('À confirmer') + '</span>';
                        break;
                    case 'confirmed':
                        status = '<span class="badge badge-success">' + _t('Confirmé') + '</span>';
                        break;
                    case 'modified':
                        status = '<span class="badge badge-warning">' + _t('Modifié') + '</span>';
                        break;
                    case 'pending_approval':
                        status = '<span class="badge badge-danger">' + _t('En attente') + '</span>';
                        break;
                    default:
                        status = '<span class="badge badge-secondary">' + slot.portal_status + '</span>';
                }
                html += '<p><strong>' + _t('Statut') + ':</strong> ' + status + '</p>';
            }
            
            html += '<div class="mt-2">';
            html += '<a href="/my/planning/slot/' + slot.id + '" class="btn btn-sm btn-primary"><i class="fa fa-eye"></i> ' + _t('Voir') + '</a> ';
            
            if (slot.portal_status === 'draft') {
                html += '<a href="/my/planning/slot/' + slot.id + '/confirm" class="btn btn-sm btn-success o_planning_slot_confirm" data-slot-id="' + slot.id + '"><i class="fa fa-check"></i> ' + _t('Confirmer') + '</a> ';
            }
            
            if (slot.portal_can_modify) {
                html += '<a href="/my/planning/slot/' + slot.id + '/modify" class="btn btn-sm btn-warning o_planning_slot_modify" data-slot-id="' + slot.id + '"><i class="fa fa-pencil"></i> ' + _t('Modifier') + '</a> ';
            }
            
            html += '<a href="/my/planning/slot/' + slot.id + '/exchange" class="btn btn-sm btn-info o_planning_slot_exchange" data-slot-id="' + slot.id + '"><i class="fa fa-exchange"></i> ' + _t('Échanger') + '</a>';
            html += '</div>';
            
            html += '</div>';
            return html;
        },

        /**
         * Gère le clic sur un événement du calendrier
         *
         * @private
         * @param {Object} info - Informations sur l'événement cliqué
         */
        _onEventClick(info) {
            const slotId = info.event.id;
            window.location.href = '/my/planning/slot/' + slotId;
        },

        /**
         * Gère le clic sur le bouton de confirmation d'un créneau
         *
         * @private
         * @param {Event} ev - Événement du navigateur
         */
        _onConfirmSlot(ev) {
            ev.preventDefault();
            const slotId = $(ev.currentTarget).data('slot-id');
            
            ajax.jsonRpc('/planning/api/slot/confirm', 'call', {
                slot_id: slotId
            }).then((data) => {
                if (data.success) {
                    self.calendar.refetchEvents();
                    self.displayNotification({
                        type: 'success',
                        title: _t('Succès'),
                        message: data.message || _t('Créneau confirmé avec succès'),
                        sticky: false
                    });
                } else {
                    self.displayNotification({
                        type: 'danger',
                        title: _t('Erreur'),
                        message: data.error || _t('Erreur lors de la confirmation du créneau'),
                        sticky: false
                    });
                }
            }).guardedCatch(function (error) {
                self.displayNotification({
                    type: 'danger',
                    title: _t('Erreur'),
                    message: _t('Erreur lors de la communication avec le serveur'),
                    sticky: false
                });
            });
        },

        /**
         * Gère le clic sur le bouton de modification d'un créneau
         *
         * @private
         * @param {Event} ev - Événement du navigateur
         */
        _onModifySlot(ev) {
            ev.preventDefault();
            const slotId = $(ev.currentTarget).data('slot-id');
            window.location.href = '/my/planning/slot/' + slotId + '/modify';
        },

        /**
         * Gère le clic sur le bouton d'échange d'un créneau
         *
         * @private
         * @param {Event} ev - Événement du navigateur
         */
        _onExchangeSlot(ev) {
            ev.preventDefault();
            const slotId = $(ev.currentTarget).data('slot-id');
            window.location.href = '/my/planning/slot/' + slotId + '/exchange';
        }
    });

    return publicWidget.registry.PlanningCalendar;
});
