(() => {
  const forms = document.querySelectorAll('.js-assignment-action');
  forms.forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (form.dataset.submitting === 'true') return;
      form.dataset.submitting = 'true';
      form.setAttribute('aria-busy', 'true');
      const button = form.querySelector('button[type="submit"]');
      const feedback = form.querySelector('.action-feedback');
      const originalButtonText = button ? button.textContent : '';
      if (button) {
        button.disabled = true;
        button.textContent = 'Saving…';
      }
      if (feedback) {
        feedback.setAttribute('role', 'status');
        feedback.textContent = 'Saving assignment…';
      }
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!response.headers.get('content-type')?.includes('application/json')) {
          throw new Error(response.redirected
            ? 'Your session may have expired. Sign in again, then retry.'
            : 'The server returned an unexpected response. Refresh the page and try again.');
        }
        const result = await response.json();
        if (!response.ok || !result.success) {
          throw new Error(result.message || 'The request could not be completed. Refresh and try again.');
        }
        if (feedback) feedback.textContent = result.message || form.dataset.success || 'Saved.';
        window.setTimeout(() => window.location.reload(), 700);
      } catch (error) {
        if (feedback) {
          feedback.setAttribute('role', 'alert');
          feedback.textContent = error.message || 'A network error prevented the change. Check your connection and try again.';
        }
        form.dataset.submitting = 'false';
        form.removeAttribute('aria-busy');
        if (button) {
          button.disabled = false;
          button.textContent = originalButtonText;
        }
      }
    });
  });
})();
