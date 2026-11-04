'use strict';
'require view';
'require form';

return view.extend({
	render: function () {
		var m = new form.Map('noisycompany', _('NoisyCompany'),
			_('Rare, plausible DNS and web activity that dilutes what your ISP sees. ' +
			  'Eco preset: a few MB per day, nothing at night, state kept in RAM.'));
		var s = m.section(form.NamedSection, 'main', 'noisycompany');
		var o;

		o = s.option(form.Flag, 'enabled', _('Enable'));
		o.rmempty = false;

		o = s.option(form.ListValue, 'preset', _('Preset'));
		o.value('eco', _('Eco (about 3 MB/day)'));
		o.value('balanced', _('Balanced'));
		o.value('max', _('Max'));

		o = s.option(form.Value, 'daily_mb', _('Daily cap (MB)'),
			_('Hard limit, never exceeded.'));
		o.datatype = 'and(ufloat,min(0.5),max(200))';

		o = s.option(form.DynamicList, 'active_hours', _('Active hours'),
			_('HH:MM-HH:MM, nothing outside.'));
		o.validate = function (id, v) {
			return /^\d{2}:\d{2}-\d{2}:\d{2}$/.test(v) ? true : _('Expected HH:MM-HH:MM');
		};

		o = s.option(form.Flag, 'locale_packs', _('Personas in your language'));
		o = s.option(form.Flag, 'weekly_rhythm', _('Weekly rhythm'),
			_('Busier on evenings, later mornings on weekends.'));
		return m.render();
	}
});
