odoo.define('portal_planning.portal', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const core = require('web.core');
    const time = require('web.time');
    const ajax = require('web.ajax');
    const _t = core._t;

    publicWidget.registry.PortalPlanning = publicWidget.Widget.extend({
        selector: '.o_portal_planning',
        events: {
            'click .o_planning_confirm': '_onConfirmPlanning',
            'click .o_planning_modify': '_onModifyPlanning',
            'click .o_planning_exchange': '_onExchangePlanning',
            'click .o_planning_cancel_modification': '_onCancelModification',
            'click .o_planning_cancel_exchange': '_onCancelExchange',
            'submit .o_planning_modification_form': '_onSubmitModification',
            'submit .o_planning_exchange_form': '_onSubmitExchange',
            'change .o_planning_filter': '_onFilterChange',
            'change #planning_date_range': '_onDateRangeChange',
            'click .o_planning_show_details': '_onToggleDetails',
        },

        /**
         * @override
         */
        start: function () {
            this._initDatePickers();
            this._initTooltips();
            return this._super.apply(this, arguments);
        },

        /**
         * Initialize date pickers for modification forms
         * @private
         */
        _initDatePickers: function () {
            const self = this;
            const datepickerOptions = {
                minDate: moment().startOf('day'),
                useCurrent: false,
                locale: moment.locale(),
                format: time.getLangDatetimeFormat(),
                icons: {
                    time: 'fa fa-clock-o',
                    date: 'fa fa-calendar',
                    up: 'fa fa-chevron-up',
                    down: 'fa fa-chevron-down',
                    previous: 'fa fa-chevron-left',
                    next: 'fa fa-chevron-right',
                    today: 'fa fa-calendar-check-o',
                    clear: 'fa fa-delete',
                    close: 'fa fa-times'
                },
            };

            // Initialize start date picker
            this.$el.find('.o_planning_datetime_start').each(function () {
                const $input = $(this);
                $input.datetimepicker(datepickerOptions);

                // When start date changes, update end date min value
                $input.on('change.datetimepicker', function (e) {
                    const $endDate = $input.closest('form').find('.o_planning_datetime_end');
                    if ($endDate.length) {
                        $endDate.datetimepicker('minDate', e.date);
                    }
                });
            });

            // Initialize end date picker
            this.$el.find('.o_planning_datetime_end').each(function () {
                const $input = $(this);
                const startDate = $input.closest('form').find('.o_planning_datetime_start').val();
                
                const endOptions = Object.assign({}, datepickerOptions);
                if (startDate) {
                    endOptions.minDate = moment(startDate, time.getLangDatetimeFormat());
                }
                
                $input.datetimepicker(endOptions);
            });
        },

        /**
         * Initialize tooltips
         * @private
         */
        _initTooltips: function () {
            this.$('[data-toggle="tooltip"]').tooltip();
        },

        /**
         * Handle planning confirmation
         * @private
         * @param {Event} ev
         */
        _onConfirmPlanning: function (ev) {
            ev.preventDefault();
            const $button = $(ev.currentTarget);
            const slotId = $button.data('slot-id');

            this._rpc({
                route: '/my/planning/confirm',
                params: {
                    slot_id: slotId,
                },
            }).then(function (result) {
                if (result.success) {
                    window.location.reload();
                } else {
                    self._showNotification('error', result.error || _t('An error occurred during confirmation.'));
                }
            }).guardedCatch(function (error) {
                self._showNotification('error', _t('An error occurred during confirmation.'));
            });
        },

        /**
         * Handle planning modification button click
         * @private
         * @param {Event} ev
         */
        _onModifyPlanning: function (ev) {
            ev.preventDefault();
            const $button = $(ev.currentTarget);
            const slotId = $button.data('slot-id');
            const $slot = $button.closest('.planning-slot');
            
            // Toggle modification form
            $slot.find('.o_planning_modification_form_container').toggleClass('d-none');
            
            // Initialize date pickers if form is shown
            if (!$slot.find('.o_planning_modification_form_container').hasClass('d-none')) {
                this._initDatePickers();
            }
        },

        /**
         * Handle planning exchange button click
         * @private
         * @param {Event} ev
         */
        _onExchangePlanning: function (ev) {
            ev.preventDefault();
            const $button = $(ev.currentTarget);
            const slotId = $button.data('slot-id');
            
            // Redirect to exchange form
            window.location.href = '/my/planning/exchange/new?slot_id=' + slotId;
        },

        /**
         * Handle modification form submission
         * @private
         * @param {Event} ev
         */
        _onSubmitModification: function (ev) {
            ev.preventDefault();
            const self = this;
            const $form = $(ev.currentTarget);
            const formData = $form.serializeArray();
            
            ajax.post($form.attr('action'), formData).then(function (result) {
                result = JSON.parse(result);
                if (result.success) {
                    window.location.reload();
                } else {
                    self._showNotification('error', result.error || _t('An error occurred during modification.'));
                }
            }).guardedCatch(function (error) {
                self._showNotification('error', _t('An error occurred during modification.'));
            });
        },

        /**
         * Handle exchange form submission
         * @private
         * @param {Event} ev
         */
        _onSubmitExchange: function (ev) {
            ev.preventDefault();
            const self = this;
            const $form = $(ev.currentTarget);
            const formData = $form.serializeArray();
            
            ajax.post($form.attr('action'), formData).then(function (result) {
                result = JSON.parse(result);
                if (result.success) {
                    window.location.href = '/my/planning/exchanges';
                } else {
                    self._showNotification('error', result.error || _t('An error occurred during exchange request.'));
                }
            }).guardedCatch(function (error) {
                self._showNotification('error', _t('An error occurred during exchange request.'));
            });
        },

        /**
         * Handle cancellation of modification
         * @private
         * @param {Event} ev
         */
        _onCancelModification: function (ev) {
            ev.preventDefault();
            const $button = $(ev.currentTarget);
            const $form = $button.closest('.o_planning_modification_form_container');
            
            // Hide form
            $form.addClass('d-none');
            
            // Reset form
            $form.find('form')[0].reset();
        },

        /**
         * Handle cancellation of exchange
         * @private
         * @param {Event} ev
         */
        _onCancelExchange: function (ev) {
            ev.preventDefault();
            window.history.back();
        },

        /**
         * Handle filter change
         * @private
         * @param {Event} ev
         */
        _onFilterChange: function (ev) {
            const $form = $(ev.currentTarget).closest('form');
            $form.submit();
        },

        /**
         * Handle date range change
         * @private
         * @param {Event} ev
         */
        _onDateRangeChange: function (ev) {
            const $form = $(ev.currentTarget).closest('form');
            $form.submit();
        },

        /**
         * Toggle planning slot details
         * @private
         * @param {Event} ev
         */
        _onToggleDetails: function (ev) {
            ev.preventDefault();
            const $button = $(ev.currentTarget);
            const $details = $button.closest('.planning-slot').find('.slot-details');
            
            $details.toggleClass('d-none');
            $button.find('i').toggleClass('fa-chevron-down fa-chevron-up');
            
            const isVisible = !$details.hasClass('d-none');
            $button.find('span').text(isVisible ? _t('Hide Details') : _t('Show Details'));
        },

        /**
         * Show notification
         * @private
         * @param {String} type - Type of notification (success, error, warning, info)
         * @param {String} message - Message to display
         */
        _showNotification: function (type, message) {
            const $notification = $('<div>').addClass('o_portal_planning_notification ' + type).text(message);
            $('body').append($notification);
            
            // Auto remove after 5 seconds
            setTimeout(function () {
                $notification.fadeOut(300, function () {
                    $(this).remove();
                });
            }, 5000);
        }
    });

    return publicWidget.registry.PortalPlanning;
});
