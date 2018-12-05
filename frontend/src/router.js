import Vue from 'vue'
import Router from 'vue-router'
import Overview from '@/components/VOverview'
import Result from '@/components/VResult'
import Person from '@/components/VDetailPerson'
import Organisation from '@/components/VDetailOrganisation'
import Search from '@/api/Search'
import { SearchMultipleFields } from '@/api/SearchMultipleFields'

Vue.use(Router)

export default new Router({
  mode: 'history',
  base: process.env.BASE_URL,
  routes: [
    {
      path: '/',
      name: 'home',
      component: Overview
    },
    {
      path: '/result',
      name: 'result',
      component: Result,
      props: true,
      beforeEnter (to, from, next) {
        SearchMultipleFields(to.query.q, ['name', 'locations', 'departments'])
          .then(res => {
            let results = []
            res.forEach(result => {
              results = results.concat(result)
            })
            to.params.results = results
          })
          .catch(() => {
            to.params.results = []
          })
          .finally(() => {
            next()
          })
      }
    },
    {
      path: '/person/:uuid',
      name: 'person',
      component: Person,
      props: true,
      beforeEnter (to, from, next) {
        Search.employees('uuid', to.params.uuid)
          .then(res => {
            to.params.result = JSON.parse(res.response.docs[0].document)
            return res
          })
          .finally(() =>
            next()
          )
      }
    },
    {
      path: '/organisation/:uuid',
      name: 'organisation',
      component: Organisation,
      props: true,
      beforeEnter (to, from, next) {
        Search.departments('uuid', to.params.uuid)
          .then(res => {
            to.params.result = JSON.parse(res.response.docs[0].document)
            return res
          })
          .finally(() =>
            next()
          )
      }
    }
  ]
})
