(() => {
  document.querySelectorAll('.js-server-error-form').forEach((form) => {
    let firstInvalid = null;
    form.querySelectorAll('.field').forEach((field) => {
      const error = field.querySelector('.form-errors[id]');
      const label = field.querySelector('label[for]');
      const control = label && document.getElementById(label.htmlFor);
      if (!error || !control) return;

      control.setAttribute('aria-invalid', 'true');
      const descriptions = new Set((control.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
      descriptions.add(error.id);
      control.setAttribute('aria-describedby', [...descriptions].join(' '));
      if (!firstInvalid && !control.disabled) firstInvalid = control;
    });

    const target = firstInvalid || form.querySelector('#form-non-field-errors');
    if (target) target.focus();
  });
})();
