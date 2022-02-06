# If DESTDIR is not specified, default to /
ifndef DESTDIR
DESTDIR=/
endif

# python sitelib
SITELIB=$(shell python3 -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")

all:
	@echo "Valid Commands:"
	@echo "  make install MODE=distro DESTDIR=/path/to/somewhere"
	@echo "    install files into DESTDIR"
	@echo "    / if no DESTDIR is specified"
	
install:
	### Install into DESTDIR
	
	# mod_wsgi script
	mkdir -p ${DESTDIR}/usr/share/InstantMiror
	install -m 644 src/InstantMirror.wsgi ${DESTDIR}/usr/share/InstantMiror
	# %config(noreplace) Apache configuration file
	mkdir -p ${DESTDIR}/etc/httpd/conf.d/
	[ ! -e ${DESTDIR}/etc/httpd/conf.d/InstantMirror.conf ] && install -m 644 src/InstantMirror.httpd.conf ${DESTDIR}/etc/httpd/conf.d/InstantMirror.conf || :
