# If DESTDIR is not specified, default to /
ifndef DESTDIR
DESTDIR=/
endif

# python sitelib
SITELIB=$(shell python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")

all:
	@echo "Valid Commands:"
	@echo "  make install MODE=distro DESTDIR=/path/to/somewhere"
	@echo "    install files into DESTDIR"
	@echo "    / if no DESTDIR is specified"
	
install:
	### Install into DESTDIR
	
	# mod_python script
	mkdir -p ${SITELIB}
	install -m 644 src/InstantMirror.py ${SITELIB}
	# %config(noreplace) Apache configuration file
	mkdir -p ${DESTDIR}/etc/httpd/conf.d/
	install -m 644 src/InstantMirror.httpd.conf ${DESTDIR}/etc/httpd/conf.d/

	exit 0 # TODO: Implement daemon and init scripts then remove this line

	# daemon
	mkdir -p ${DESTDIR}/usr/bin/
	install -pm 755 src/mirrormonitord ${DESTDIR}/usr/bin/
	# init script
	mkdir -p ${DESTDIR}/etc/rc.d/init.d/
	install -pm 644 src/mirrormonitord.init ${DESTDIR}/etc/rc.d/init.d/
	mkdir -p ${DESTDIR}/etc/mirrormonitor/

	# default configuration, replaced by package every upgrade, not for user editing
	install -pm 644 src/distro.conf ${DESTDIR}/etc/mirrormonitor/
	# %config(noreplace) to be modifiable by user, overrides settings in distro.conf
	install -pm 644 src/local.conf  ${DESTDIR}/etc/mirrormonitor/
	# drop arbitrary repo definitions here
	mkdir -p ${DESTDIR}/etc/mirrormonitor/conf.d/

	# this directory contains backend libraries if we end up needing them
	CODEDIR=${DESTDIR}/usr/share/InstantMirror/
	mkdir -p ${CODEDIR}
	install -m 644 src/foo.py ${CODEDIR}
	install -m 644 src/bar.py ${CODEDIR}
	install -m 644 src/baz.py ${CODEDIR}
